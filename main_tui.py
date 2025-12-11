#!/usr/bin/env python3
"""간단한 텍스트 기반 TUI.

- 기본 설정(심볼/수량/지연)을 화면에서 바로 바꾸고 실행할 수 있습니다.
- 모든 네트워크 요청은 main.py의 BackpackClient를 그대로 사용합니다.
- 입력 시 오류가 나면 그대로 출력되어 ChatGPT에 전달해 디버깅할 수 있습니다.
"""
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from main import BackpackClient, print_status, run_volume


async def _ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def _safe_float(text: str, default: float) -> float:
    try:
        return float(text)
    except ValueError:
        print("숫자로 해석할 수 없습니다. 기존 값을 유지합니다.")
        return default


async def _status_screen(client: BackpackClient, symbol: str, stop_event: asyncio.Event, interval: float = 1.0) -> None:
    """잔고/포지션을 주기적으로 동일 화면에 갱신한다."""
    while not stop_event.is_set():
        # ANSI 시퀀스로 화면을 지우고 커서를 맨 위로 이동
        print("\033[2J\033[H", end="")
        print("[잔고/포지션 실시간 보기] (Enter를 누르면 메뉴로 돌아갑니다)\n")
        try:
            await print_status(client, symbol)
        except Exception as exc:  # pragma: no cover - 인터랙티브 로그
            print(f"상태 업데이트 실패: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def tui_loop() -> None:
    load_dotenv()
    base_url = os.getenv("BACKPACK_BASE_URL", "https://api.backpack.exchange")
    window_ms = os.getenv("BACKPACK_WINDOW_MS", "5000")
    debug = (input("디버그 로그 출력? (y/N): ") or "n").lower().startswith("y")

    client = BackpackClient(
        base_url=base_url,
        window_ms=window_ms,
        debug=debug,
    )

    symbol = "SOL"
    size = 0.01
    order_count = 1
    cycles = 1
    interval_min = 1.0
    interval_max = 3.0

    async def shutdown() -> None:
        await client.aclose()

    try:
        while True:
            print("\n===== Backpack 터미널 =====")
            print("오류가 보이면 그대로 복사해 ChatGPT에 알려 주세요. 모의 모드는 키 미입력, 실거래는 키 입력 상태입니다.")
            cycle_text = "무한" if cycles == 0 else str(cycles)
            print(
                f"현재 설정: 심볼={symbol}, 수량={size}, 각 방향 주문={order_count}회, "
                f"세트 반복={cycle_text}, 대기={interval_min}~{interval_max}s"
            )
            print(f"API 모드={'모의' if client.simulated else '실거래'} | 디버그={'ON' if client.debug else 'OFF'}")
            print("1) 잔고/포지션 확인")
            print("2) 현재 설정으로 주문 실행")
            print("3) 모든 포지션 청산")
            print("4) 설정 변경")
            print("5) 종료")
            choice = (await _ainput("선택: ")).strip()

            if choice == "1":
                stop_event = asyncio.Event()
                status_task = asyncio.create_task(_status_screen(client, symbol, stop_event))
                await _ainput("")  # Enter 대기
                stop_event.set()
                await status_task
            elif choice == "2":
                try:
                    await run_volume(client, symbol, size, order_count, cycles, interval_min, interval_max)
                except Exception as exc:
                    print(f"주문 실행 실패: {exc}")
            elif choice == "3":
                try:
                    await client.close_all_positions(symbol)
                except Exception as exc:
                    print(f"청산 실패: {exc}")
            elif choice == "4":
                symbol_input = (await _ainput("심볼 (예: SOL): ")).strip()
                if symbol_input:
                    symbol = symbol_input.upper()

                size = _safe_float(await _ainput("1회 주문 수량 (소수 가능): "), size)

                order_input = _safe_float(await _ainput("각 방향 주문 횟수(정수): "), float(order_count))
                if order_input >= 1:
                    order_count = int(order_input)
                else:
                    print("1 이상으로 입력해야 합니다. 기존 값 유지")

                cycles_input = _safe_float(await _ainput("세트 반복 횟수 (0=무한): "), float(cycles))
                if cycles_input >= 0:
                    cycles = int(cycles_input)
                else:
                    print("0 이상으로 입력해야 합니다. 기존 값 유지")

                old_min, old_max = interval_min, interval_max
                interval_min = _safe_float(await _ainput("최소 대기 시간(초): "), interval_min)
                interval_max = _safe_float(await _ainput("최대 대기 시간(초): "), interval_max)
                if interval_min < 0 or interval_max < 0 or interval_min > interval_max:
                    print("대기 시간은 0 이상이며 최소<=최대 여야 합니다. 기존 값을 유지합니다.")
                    interval_min, interval_max = old_min, old_max
            elif choice == "5":
                print("종료합니다.")
                break
            else:
                print("메뉴에서 숫자를 선택해 주세요.")
    finally:
        await shutdown()


def main() -> None:
    asyncio.run(tui_loop())


if __name__ == "__main__":
    main()
