#!/usr/bin/env python3
"""
이미지 업로드 테스트 v2

Playwright expect_file_chooser 사용
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


# 테스트 이미지 경로
TEST_IMAGE = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"


async def test_image_upload():
    """이미지 업로드 테스트 v2"""

    print("\n" + "="*60)
    print("이미지 업로드 테스트 v2 (file_chooser 방식)")
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    # 이미지 파일 확인
    if not Path(TEST_IMAGE).exists():
        print(f"테스트 이미지가 없습니다: {TEST_IMAGE}")
        return

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        screenshot_dir="data/image_upload_v2"
    )

    Path(config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

        # 글쓰기 페이지로 이동
        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 임시저장 팝업 처리
        for _ in range(3):
            dismissed = await publisher._dismiss_temp_save_popup()
            if not dismissed:
                break
            await asyncio.sleep(0.3)

        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_start.png")

        # 본문으로 이동
        print("\n1. 본문 영역 클릭...")
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        await publisher._type_text("이미지 업로드 테스트입니다.\n\n")
        await asyncio.sleep(0.3)

        # 2. 이미지 버튼 탐색
        print("\n2. 이미지 버튼 탐색...")

        # 이미지 관련 모든 버튼/요소 조사
        image_elements = await publisher._evaluate_js("""
            (() => {
                const results = [];

                // data-name="image" 버튼
                const imageBtn = document.querySelector('[data-name="image"]');
                if (imageBtn) {
                    const rect = imageBtn.getBoundingClientRect();
                    results.push({
                        type: 'data-name-image',
                        selector: '[data-name="image"]',
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                        html: imageBtn.outerHTML.substring(0, 200)
                    });
                }

                // 모든 file input 찾기
                const fileInputs = document.querySelectorAll('input[type="file"]');
                fileInputs.forEach((inp, i) => {
                    const rect = inp.getBoundingClientRect();
                    results.push({
                        type: 'file-input',
                        index: i,
                        accept: inp.accept,
                        id: inp.id,
                        className: inp.className,
                        visible: rect.width > 0 && rect.height > 0,
                        html: inp.outerHTML.substring(0, 200)
                    });
                });

                // 사진/이미지 텍스트가 있는 버튼
                const btns = document.querySelectorAll('button');
                btns.forEach(btn => {
                    const text = btn.innerText?.trim() || '';
                    const ariaLabel = btn.getAttribute('aria-label') || '';
                    if (text.includes('사진') || text.includes('이미지') ||
                        ariaLabel.includes('사진') || ariaLabel.includes('이미지')) {
                        const rect = btn.getBoundingClientRect();
                        results.push({
                            type: 'text-button',
                            text: text,
                            ariaLabel: ariaLabel,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        });
                    }
                });

                return results;
            })()
        """)

        print(f"   발견된 이미지 관련 요소: {len(image_elements)}개")
        for elem in image_elements:
            print(f"   - {elem.get('type')}: {elem}")

        # 3. 방법 1: expect_file_chooser 사용
        print("\n3. 방법 1: expect_file_chooser로 이미지 업로드 시도...")

        image_btn = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="image"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)

        if image_btn and image_btn.get("found"):
            try:
                # file_chooser 이벤트 대기 + 버튼 클릭을 동시에
                async with publisher.page.expect_file_chooser(timeout=5000) as fc_info:
                    await publisher._click_at(*image_btn["coords"])
                    print(f"   이미지 버튼 클릭: {image_btn['coords']}")

                file_chooser = await fc_info.value
                await file_chooser.set_files(TEST_IMAGE)
                print(f"   파일 선택 완료: {TEST_IMAGE}")
                await asyncio.sleep(3)  # 업로드 대기

            except Exception as e:
                print(f"   file_chooser 방식 실패: {e}")
                print("   → 방법 2 시도...")

                # 4. 방법 2: 버튼 클릭 후 모달에서 file input 찾기
                await asyncio.sleep(1)

                # 모달이 열렸는지 확인
                modal_info = await publisher._evaluate_js("""
                    (() => {
                        // 이미지 업로드 모달/팝업 찾기
                        const modals = document.querySelectorAll('.se-popup, .se-image-popup, [class*="image-upload"]');
                        for (const modal of modals) {
                            const style = window.getComputedStyle(modal);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                const fileInput = modal.querySelector('input[type="file"]');
                                if (fileInput) {
                                    return {
                                        found: true,
                                        modalClass: modal.className,
                                        hasFileInput: true
                                    };
                                }
                                return {
                                    found: true,
                                    modalClass: modal.className,
                                    hasFileInput: false,
                                    html: modal.innerHTML.substring(0, 500)
                                };
                            }
                        }
                        return { found: false };
                    })()
                """)
                print(f"   모달 정보: {modal_info}")

                # 5. 방법 3: 모든 file input에 직접 파일 설정
                print("\n   방법 3: 모든 file input에 직접 파일 설정 시도...")

                file_inputs = await publisher.page.query_selector_all('input[type="file"]')
                print(f"   발견된 file input 수: {len(file_inputs)}")

                for i, fi in enumerate(file_inputs):
                    try:
                        # hidden이라도 시도
                        await fi.set_input_files(TEST_IMAGE)
                        print(f"   file input[{i}]에 파일 설정 성공!")
                        await asyncio.sleep(3)
                        break
                    except Exception as e2:
                        print(f"   file input[{i}] 실패: {e2}")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_after_upload.png")

        # 6. 업로드 결과 확인
        print("\n4. 업로드 결과 확인...")

        # 에디터에 이미지가 삽입되었는지 확인
        image_check = await publisher._evaluate_js("""
            (() => {
                // 에디터 내 이미지 컴포넌트 찾기
                const imageComponents = document.querySelectorAll('.se-component.se-image, .se-image-resource');
                return {
                    count: imageComponents.length,
                    found: imageComponents.length > 0
                };
            })()
        """)

        print(f"   에디터 내 이미지 컴포넌트: {image_check}")

        # 7. 인용구 추가
        print("\n5. 인용구 추가...")

        quote_btn = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="quotation"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)

        if quote_btn and quote_btn.get("found"):
            await publisher._click_at(*quote_btn["coords"])
            await asyncio.sleep(0.5)
            await publisher._type_text("이미지 업로드 테스트 인용구입니다!")
            await asyncio.sleep(0.3)
            print("   인용구 삽입 완료")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_final.png")

        print("\n" + "="*60)
        print("테스트 완료")
        print(f"이미지 업로드: {'성공' if image_check.get('found') else '실패'}")
        print(f"스크린샷: {config.screenshot_dir}/{timestamp}_*.png")
        print("="*60)

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_image_upload())
