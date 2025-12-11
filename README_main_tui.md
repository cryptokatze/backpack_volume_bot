# main_tui.py 왕초보 실행 가이드

처음부터 끝까지 그대로 따라 하면 `main_tui.py`를 실행할 수 있는 초간단 안내서입니다. 가상환경 만들기부터 .env 작성, 실행 후 조작까지 한 번에 정리했습니다.

## 0. main_tui.py가 하는 일
- 터미널 화면에서 심볼/수량/대기 시간 등을 설정하고, 매수→매도 주문 세트를 반복 실행하는 텍스트 UI입니다.
- `.env`에 API 키가 없으면 자동으로 **모의 모드**(실제 주문 없음)로, 키를 넣으면 **실거래 모드**로 동작합니다.

## 1. Python 준비 확인
- 터미널(또는 PowerShell)에서 버전을 확인합니다. 3.10 이상이면 OK.

```bash
python --version
# 또는
python3 --version
```

## 2. 코드 내려받기
### (추천) Git 사용
```bash
git clone https://github.com/cryptokatze/backpack_auto_vol.git
cd backpack_auto_vol
```

### ZIP으로 받기
1) GitHub에서 `Download ZIP` → 압축 풀기  
2) 터미널에서 풀린 폴더로 이동:
```bash
cd path/to/backpack_auto_vol
```

## 3. 가상환경 만들기 & 켜기
프로젝트 폴더 안에서 아래를 실행합니다.

```bash
python -m venv .venv
```

- macOS / Linux:
```bash
source .venv/bin/activate
```
- Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```

터미널 프롬프트에 `(venv)` 비슷한 표시가 뜨면 켜진 것입니다.

## 4. 필요한 라이브러리 설치
가상환경이 켜진 상태에서:

```bash
pip install -r requirements.txt
```

## 5. .env 파일 만들기
프로젝트 루트(README와 main_tui.py가 있는 위치)에 `.env` 파일을 새로 만듭니다. 아래 둘 중 하나로 채워 넣으세요.

### 5-1) 모의 모드(처음에는 이걸 추천)
```
BACKPACK_API_KEY=
BACKPACK_API_SECRET=
BACKPACK_BASE_URL=https://api.backpack.exchange
BACKPACK_WINDOW_MS=5000
```
- 키를 비워 두면 실제 주문 없이 흐름만 테스트합니다.

### 5-2) 실거래 모드 (주문이 실제로 나감 ⚠️)
```
BACKPACK_API_KEY=여기에_API_KEY
BACKPACK_API_SECRET=여기에_API_SECRET
BACKPACK_BASE_URL=https://api.backpack.exchange
BACKPACK_WINDOW_MS=5000
```
- 공백/따옴표 없이 붙여 넣으세요.
- 먼저 모의 모드로 충분히 테스트 후, 정말 필요할 때만 키를 넣는 것을 권장합니다.

## 6. (선택) .env가 읽히는지 빠른 점검
```bash
python - << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()
print("API_KEY =", os.getenv("BACKPACK_API_KEY"))
print("SECRET  =", os.getenv("BACKPACK_API_SECRET"))
EOF
```
- 둘 다 `None`이 아니면 성공입니다. `None`이면 파일 위치/이름을 다시 확인하세요.

## 7. main_tui.py 실행
- 가상환경이 켜진 상태로:
```bash
python main_tui.py
# 또는
python3 main_tui.py
```
- 처음에 `디버그 로그 출력? (y/N):`가 나오면 Enter(기본 N) 또는 `y` 입력.
- 화면에 **API 모드**가 `모의/실거래`로 표시됩니다. 모의 모드 문구가 보이면 키가 비어 있다는 뜻입니다.

## 8. 메뉴 사용법 한눈에 보기
실행 후 나오는 기본 메뉴:
- 1) 잔고/포지션 확인: 실시간으로 표시, Enter를 누르면 메뉴로 돌아옵니다.
- 2) 현재 설정으로 주문 실행: 기본값은 `심볼=SOL`, `수량=0.01`, `각 방향 주문 1회`, `세트 반복 1회`, `대기 1~3초`. 실행 중에는 아래 9번 단축키로 제어합니다.
- 3) 모든 포지션 청산: 현재 심볼 기준 포지션을 정리합니다.
- 4) 설정 변경: 심볼/수량/주문 횟수/반복 횟수/대기 시간을 원하는 값으로 입력합니다. 반복 횟수에 `0`을 넣으면 무한 반복입니다.
- 5) 종료: 프로그램을 닫습니다.

## 9. 주문 실행 중 단축키
주문이 돌아가는 동안 터미널에 입력할 수 있습니다.
- `p` : 일시중지
- `r` : 재개
- `q` : 현재 진행 중인 사이클을 마치고 종료
- `c` : 가능한 포지션을 청산한 뒤 종료

## 10. 자주 묻는 질문/에러
- `API 키/시크릿이 없어 모의 모드로 시작` 문구: 정상입니다. 키를 넣지 않은 상태입니다.
- `Invalid signature` 에러: Secret이 잘못됐거나 공백/줄바꿈이 섞였을 가능성이 큽니다. 새 키를 발급받아 깨끗하게 붙여 넣으세요.
- HTTP 4xx/5xx 에러: 터미널 로그 전체를 복사해 두면 원인 파악에 도움이 됩니다.

여기까지 따르면: Python 확인 → 가상환경 → 의존성 설치 → .env 작성 → `python main_tui.py` 실행 → 메뉴로 주문/청산/설정 변경까지 완료할 수 있습니다.
