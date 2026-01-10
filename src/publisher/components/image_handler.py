"""
ImageHandler - 네이버 스마트에디터 이미지 업로드

CDP DOM.setFileInputFiles()를 사용하여 숨겨진 file input에
이미지 파일을 직접 주입합니다.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger("blog_writer.image_handler")


class ImageHandler:
    """
    이미지 업로드 핸들러

    네이버 스마트에디터의 이미지 업로드를 자동화합니다.
    이미지 버튼 클릭 시 동적으로 생성되는 숨겨진 file input을
    찾아 CDP로 파일을 주입합니다.

    사용 예시:
        handler = ImageHandler(cdp_session, page)
        await handler.upload_image("/path/to/image.jpg")
        await handler.upload_images(["/path/to/img1.jpg", "/path/to/img2.png"])
    """

    # 이미지 버튼 셀렉터
    IMAGE_BUTTON_SELECTOR = '[data-name="image"]'

    # 숨겨진 file input 셀렉터 (동적 생성됨)
    FILE_INPUT_SELECTOR = '#hidden-file'

    # 지원 확장자
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.gif', '.png', '.bmp', '.heic', '.heif', '.webp'}

    # 업로드 대기 시간
    UPLOAD_TIMEOUT = 30.0

    def __init__(self, cdp_session, page):
        """
        Args:
            cdp_session: Playwright CDP 세션
            page: Playwright 페이지 객체
        """
        self.cdp = cdp_session
        self.page = page
        self._upload_count = 0

    async def upload_image(
        self,
        file_path: Union[str, Path],
        wait_for_upload: bool = True
    ) -> bool:
        """단일 이미지 업로드

        Args:
            file_path: 이미지 파일 경로
            wait_for_upload: 업로드 완료 대기 여부

        Returns:
            성공 여부
        """
        return await self.upload_images([file_path], wait_for_upload)

    async def upload_images(
        self,
        file_paths: List[Union[str, Path]],
        wait_for_upload: bool = True
    ) -> bool:
        """다중 이미지 업로드

        Args:
            file_paths: 이미지 파일 경로 리스트
            wait_for_upload: 업로드 완료 대기 여부

        Returns:
            성공 여부
        """
        # 파일 유효성 검사
        validated_paths = []
        for path in file_paths:
            path = Path(path)
            if not path.exists():
                logger.error(f"File not found: {path}")
                continue
            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                logger.error(f"Unsupported file type: {path.suffix}")
                continue
            validated_paths.append(str(path.absolute()))

        if not validated_paths:
            logger.error("No valid files to upload")
            return False

        logger.info(f"Uploading {len(validated_paths)} image(s)")

        try:
            # 1. 이미지 버튼 클릭하여 file input 활성화
            if not await self._click_image_button():
                logger.error("Failed to click image button")
                return False

            await asyncio.sleep(0.5)

            # 2. 숨겨진 file input 찾기
            file_input = await self._find_file_input()
            if not file_input:
                logger.error("Hidden file input not found")
                return False

            logger.debug(f"File input found: backendNodeId={file_input.get('backendNodeId')}")

            # 3. CDP로 파일 주입
            await self.cdp.send('DOM.setFileInputFiles', {
                'files': validated_paths,
                'backendNodeId': file_input['backendNodeId']
            })

            logger.info(f"Files injected via CDP: {validated_paths}")

            # 4. 업로드 완료 대기
            if wait_for_upload:
                success = await self._wait_for_upload_complete(len(validated_paths))
                if success:
                    self._upload_count += len(validated_paths)
                    logger.info(f"Upload complete. Total uploaded: {self._upload_count}")
                return success

            self._upload_count += len(validated_paths)
            return True

        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            return False

    async def _click_image_button(self) -> bool:
        """이미지 버튼 클릭"""
        result = await self._evaluate_js(f"""
            (() => {{
                const btn = document.querySelector('{self.IMAGE_BUTTON_SELECTOR}');
                if (btn) {{
                    const rect = btn.getBoundingClientRect();
                    return {{
                        found: true,
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2
                    }};
                }}
                return {{ found: false }};
            }})()
        """)

        if not result or not result.get('found'):
            return False

        # CDP로 클릭
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": result['x'],
            "y": result['y'],
            "button": "left",
            "clickCount": 1
        })
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": result['x'],
            "y": result['y'],
            "button": "left",
            "clickCount": 1
        })

        logger.debug("Image button clicked")
        return True

    async def _find_file_input(self, timeout: float = 3.0) -> Optional[Dict]:
        """숨겨진 file input 요소 찾기

        이미지 버튼 클릭 후 동적으로 생성되는 file input을 탐색합니다.
        """
        import time
        start = time.time()

        while time.time() - start < timeout:
            # DOM에서 file input 찾기
            doc = await self.cdp.send("DOM.getDocument")
            root_id = doc["root"]["nodeId"]

            result = await self.cdp.send("DOM.querySelector", {
                "nodeId": root_id,
                "selector": self.FILE_INPUT_SELECTOR
            })

            if result.get("nodeId", 0) != 0:
                # backendNodeId 가져오기
                node_info = await self.cdp.send("DOM.describeNode", {
                    "nodeId": result["nodeId"]
                })

                return {
                    "nodeId": result["nodeId"],
                    "backendNodeId": node_info["node"]["backendNodeId"]
                }

            await asyncio.sleep(0.2)

        return None

    async def _wait_for_upload_complete(
        self,
        expected_count: int,
        timeout: float = None
    ) -> bool:
        """업로드 완료 대기

        에디터에 이미지 컴포넌트가 삽입될 때까지 대기합니다.
        """
        timeout = timeout or self.UPLOAD_TIMEOUT
        import time
        start = time.time()

        # 업로드 전 이미지 수
        initial_count = await self._get_image_count()

        while time.time() - start < timeout:
            current_count = await self._get_image_count()

            # 새 이미지가 추가되었는지 확인
            if current_count >= initial_count + expected_count:
                logger.debug(f"Images detected: {current_count} (was {initial_count})")
                return True

            # 업로드 중 프로그레스 확인
            is_uploading = await self._check_upload_progress()
            if is_uploading:
                logger.debug("Upload in progress...")

            await asyncio.sleep(0.5)

        logger.warning(f"Upload timeout after {timeout}s")
        return False

    async def _get_image_count(self) -> int:
        """에디터 내 이미지 컴포넌트 수 확인"""
        count = await self._evaluate_js("""
            (() => {
                // 스마트에디터 이미지 컴포넌트
                const images = document.querySelectorAll(
                    '.se-image-resource, .se-component-image, [data-type="image"]'
                );
                return images.length;
            })()
        """)
        return count or 0

    async def _check_upload_progress(self) -> bool:
        """업로드 진행 중인지 확인"""
        is_uploading = await self._evaluate_js("""
            (() => {
                // 업로드 프로그레스 요소 확인
                const progress = document.querySelector(
                    '.se-upload-progress, .se-image-uploading, [class*="progress"]'
                );
                return progress !== null;
            })()
        """)
        return bool(is_uploading)

    async def _evaluate_js(self, expression: str):
        """JavaScript 평가"""
        result = await self.cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    def get_upload_count(self) -> int:
        """현재 세션에서 업로드한 이미지 수"""
        return self._upload_count

    async def close_image_selection_layer(self) -> bool:
        """이미지 선택 레이어 닫기 (ESC)"""
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })
        logger.debug("Closed image selection layer")
        return True
