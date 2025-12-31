#!/usr/bin/env python3
"""Backpack Exchange API 클라이언트 및 볼륨 거래 봇.

ED25519 서명을 사용한 API 인증과 잔고/포지션 조회, 주문 실행 기능을 제공합니다.
"""
from __future__ import annotations

import asyncio
import base64
import os
import random
import sys
from time import time
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric import ed25519
from dotenv import load_dotenv


class BackpackClient:
    """Backpack Exchange API 클라이언트."""

    def __init__(
        self,
        base_url: str = "https://api.backpack.exchange",
        window_ms: str = "5000",
        debug: bool = False,
    ) -> None:
        load_dotenv()
        self.base_url = base_url.rstrip("/")
        self.window_ms = window_ms
        self.debug = debug

        # API 키 로드
        self.api_key = os.getenv("BACKPACK_API_KEY", "").strip()
        self.api_secret = os.getenv("BACKPACK_API_SECRET", "").strip()

        # 키가 비어있으면 모의 모드
        self.simulated = not (self.api_key and self.api_secret)

        if self.simulated:
            print("API 키/시크릿이 없어 모의 모드로 시작합니다.")
            self._private_key = None
        else:
            try:
                secret_bytes = base64.b64decode(self.api_secret)
                self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_bytes)
            except Exception as e:
                print(f"API Secret 디코딩 실패: {e}")
                print("모의 모드로 전환합니다.")
                self.simulated = True
                self._private_key = None

        # HTTP 클라이언트
        self._client = httpx.AsyncClient(timeout=30.0)

        # 실행 제어 플래그
        self.paused = False
        self.stop_requested = False
        self.close_and_stop = False

    async def aclose(self) -> None:
        """HTTP 클라이언트 종료."""
        await self._client.aclose()

    def _sign(self, instruction: str, params: dict[str, Any] | None = None) -> dict[str, str]:
        """ED25519 서명을 생성하고 인증 헤더를 반환합니다."""
        timestamp = int(time() * 1000)
        window = self.window_ms

        # 서명 문자열 생성
        sign_str = f"instruction={instruction}"

        if params:
            sorted_params = []
            for key, value in sorted(params.items()):
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = str(value).lower()
                sorted_params.append(f"{key}={value}")
            if sorted_params:
                sign_str += "&" + "&".join(sorted_params)

        sign_str += f"&timestamp={timestamp}&window={window}"

        if self.debug:
            print(f"[DEBUG] Sign string: {sign_str}")

        # 서명 생성
        signature_bytes = self._private_key.sign(sign_str.encode())
        encoded_signature = base64.b64encode(signature_bytes).decode()

        return {
            "X-API-Key": self.api_key,
            "X-Signature": encoded_signature,
            "X-Timestamp": str(timestamp),
            "X-Window": window,
            "Content-Type": "application/json; charset=utf-8",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        instruction: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """API 요청을 수행합니다."""
        if self.simulated:
            if self.debug:
                print(f"[모의] {method} {endpoint} params={params} body={json_body}")
            return self._simulate_response(instruction, params, json_body)

        url = f"{self.base_url}{endpoint}"
        headers = self._sign(instruction, params or json_body)

        try:
            if method == "GET":
                response = await self._client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await self._client.post(url, headers=headers, json=json_body)
            elif method == "DELETE":
                response = await self._client.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")

            if self.debug:
                print(f"[DEBUG] {method} {url} -> {response.status_code}")
                print(f"[DEBUG] Response: {response.text[:500]}")

            if response.status_code >= 400:
                print(f"API 에러 [{response.status_code}]: {response.text}")
                return None

            if response.text:
                return response.json()
            return {}

        except Exception as e:
            print(f"요청 실패: {e}")
            return None

    def _simulate_response(
        self,
        instruction: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """모의 모드 응답을 생성합니다."""
        if instruction == "balanceQuery":
            return {
                "USDC": {"available": "1000.00", "locked": "0.00", "staked": "0.00"},
                "SOL": {"available": "10.00", "locked": "0.00", "staked": "0.00"},
            }
        elif instruction == "positionQuery":
            return []
        elif instruction == "orderExecute":
            return {
                "id": f"sim_{int(time()*1000)}",
                "symbol": json_body.get("symbol") if json_body else "SOL_USDC",
                "side": json_body.get("side") if json_body else "Bid",
                "status": "Filled",
                "quantity": json_body.get("quantity") if json_body else "0.01",
            }
        elif instruction == "orderCancel":
            return {"status": "Cancelled"}
        elif instruction == "orderCancelAll":
            return {"cancelled": 0}
        return {}

    async def get_balances(self) -> dict[str, Any] | None:
        """계정 잔고를 조회합니다."""
        return await self._request("GET", "/api/v1/capital", "balanceQuery")

    async def get_positions(self, symbol: str | None = None) -> list[Any] | None:
        """포지션을 조회합니다 (선물 거래용)."""
        params = {"symbol": f"{symbol}_USDC_PERP"} if symbol else None
        result = await self._request("GET", "/api/v1/position", "positionQuery", params=params)
        if result is None:
            return []
        return result if isinstance(result, list) else [result] if result else []

    async def get_open_orders(self, symbol: str | None = None) -> list[Any] | None:
        """열린 주문을 조회합니다."""
        params = {"symbol": f"{symbol}_USDC"} if symbol else None
        result = await self._request("GET", "/api/v1/orders", "orderQueryAll", params=params)
        return result if isinstance(result, list) else []

    async def execute_order(
        self,
        symbol: str,
        side: str,  # "Bid" (매수) or "Ask" (매도)
        quantity: float,
        order_type: str = "Market",
        price: float | None = None,
    ) -> dict[str, Any] | None:
        """주문을 실행합니다."""
        # 현물 거래 심볼 형식
        trade_symbol = f"{symbol}_USDC"

        body: dict[str, Any] = {
            "symbol": trade_symbol,
            "side": side,
            "orderType": order_type,
            "quantity": str(quantity),
        }

        if order_type == "Limit" and price is not None:
            body["price"] = str(price)
            body["timeInForce"] = "GTC"

        return await self._request("POST", "/api/v1/order", "orderExecute", json_body=body)

    async def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any] | None:
        """주문을 취소합니다."""
        params = {"symbol": f"{symbol}_USDC", "orderId": order_id}
        return await self._request("DELETE", "/api/v1/order", "orderCancel", params=params)

    async def cancel_all_orders(self, symbol: str) -> dict[str, Any] | None:
        """모든 주문을 취소합니다."""
        params = {"symbol": f"{symbol}_USDC"}
        return await self._request("DELETE", "/api/v1/orders", "orderCancelAll", params=params)

    async def close_all_positions(self, symbol: str) -> None:
        """해당 심볼의 모든 포지션을 청산합니다."""
        print(f"{symbol} 포지션 청산 시도...")

        # 열린 주문 취소
        await self.cancel_all_orders(symbol)

        # 포지션 조회 (선물)
        positions = await self.get_positions(symbol)
        if not positions:
            print("청산할 포지션이 없습니다.")
            return

        for pos in positions:
            size = float(pos.get("netSize", 0))
            if abs(size) < 0.0001:
                continue

            # 반대 방향으로 시장가 주문
            side = "Ask" if size > 0 else "Bid"
            await self.execute_order(symbol, side, abs(size), "Market")
            print(f"포지션 청산: {side} {abs(size)} {symbol}")


async def print_status(client: BackpackClient, symbol: str) -> None:
    """잔고와 포지션 상태를 출력합니다."""
    print(f"=== {symbol} 상태 ===")

    # 잔고 조회
    balances = await client.get_balances()
    if balances:
        print("\n[잔고]")
        for asset, info in balances.items():
            if isinstance(info, dict):
                available = info.get("available", "0")
                locked = info.get("locked", "0")
                if float(available) > 0 or float(locked) > 0:
                    print(f"  {asset}: 가용={available}, 잠김={locked}")
    else:
        print("[잔고] 조회 실패")

    # 포지션 조회 (선물)
    positions = await client.get_positions(symbol)
    if positions:
        print("\n[포지션]")
        for pos in positions:
            sym = pos.get("symbol", "?")
            size = pos.get("netSize", "0")
            entry = pos.get("entryPrice", "?")
            pnl = pos.get("unrealizedPnl", "0")
            print(f"  {sym}: 수량={size}, 진입가={entry}, 미실현손익={pnl}")
    else:
        print("\n[포지션] 없음")

    # 열린 주문 조회
    orders = await client.get_open_orders(symbol)
    if orders:
        print("\n[열린 주문]")
        for order in orders:
            oid = order.get("id", "?")[:8]
            side = order.get("side", "?")
            qty = order.get("quantity", "?")
            price = order.get("price", "시장가")
            status = order.get("status", "?")
            print(f"  {oid}... {side} {qty} @ {price} ({status})")
    else:
        print("\n[열린 주문] 없음")

    print()


async def run_volume(
    client: BackpackClient,
    symbol: str,
    size: float,
    order_count: int,
    cycles: int,
    interval_min: float,
    interval_max: float,
) -> None:
    """볼륨 거래를 실행합니다.

    매수 order_count회 → 매도 order_count회를 cycles번 반복합니다.
    cycles=0이면 무한 반복합니다.
    """
    print(f"\n볼륨 거래 시작: {symbol} | 수량={size} | 주문횟수={order_count} | 사이클={cycles if cycles > 0 else '무한'}")
    print("제어 키: p=일시정지, r=재개, q=종료, c=청산후종료")

    # 키 입력 처리 태스크
    input_task = asyncio.create_task(_handle_input(client))

    cycle_num = 0
    try:
        while cycles == 0 or cycle_num < cycles:
            if client.stop_requested:
                print("\n종료 요청됨.")
                break
            if client.close_and_stop:
                print("\n청산 후 종료 요청됨.")
                await client.close_all_positions(symbol)
                break

            cycle_num += 1
            print(f"\n--- 사이클 {cycle_num} ---")

            # 매수 주문
            for i in range(order_count):
                await _wait_if_paused(client)
                if client.stop_requested or client.close_and_stop:
                    break

                result = await client.execute_order(symbol, "Bid", size, "Market")
                status = "성공" if result else "실패"
                print(f"  매수 {i+1}/{order_count}: {status}")

                await _random_delay(interval_min, interval_max)

            if client.stop_requested or client.close_and_stop:
                break

            # 매도 주문
            for i in range(order_count):
                await _wait_if_paused(client)
                if client.stop_requested or client.close_and_stop:
                    break

                result = await client.execute_order(symbol, "Ask", size, "Market")
                status = "성공" if result else "실패"
                print(f"  매도 {i+1}/{order_count}: {status}")

                await _random_delay(interval_min, interval_max)

        print("\n볼륨 거래 완료.")

    finally:
        input_task.cancel()
        try:
            await input_task
        except asyncio.CancelledError:
            pass

        # 플래그 초기화
        client.paused = False
        client.stop_requested = False
        client.close_and_stop = False


async def _handle_input(client: BackpackClient) -> None:
    """실행 중 키 입력을 처리합니다."""
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            cmd = line.strip().lower()

            if cmd == "p":
                client.paused = True
                print("[일시정지됨 - r로 재개]")
            elif cmd == "r":
                client.paused = False
                print("[재개됨]")
            elif cmd == "q":
                client.stop_requested = True
                print("[종료 예약됨]")
            elif cmd == "c":
                client.close_and_stop = True
                print("[청산 후 종료 예약됨]")
    except asyncio.CancelledError:
        pass


async def _wait_if_paused(client: BackpackClient) -> None:
    """일시정지 상태면 대기합니다."""
    while client.paused and not client.stop_requested and not client.close_and_stop:
        await asyncio.sleep(0.1)


async def _random_delay(min_sec: float, max_sec: float) -> None:
    """랜덤 대기 시간."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def main() -> None:
    """메인 함수."""
    load_dotenv()

    client = BackpackClient(debug=True)

    try:
        await print_status(client, "SOL")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
