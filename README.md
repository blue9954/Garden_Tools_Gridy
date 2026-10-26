# Garden Tools Gridy

사진 2~3장을 세로로 합쳐 여백이 있는 이미지 한 장으로 저장하는 Windows 앱입니다. 모든 사진 처리는 컴퓨터 안에서 진행합니다.

## 실행

프로젝트 루트의 `Gridy.cmd`를 실행합니다. 최신 검증된 빌드로 연결됩니다. 현재 앱 버전은 **1.0.3**이며 변경 이력은 `CHANGELOG.md`에 있습니다. 배포 ZIP을 사용하는 경우 압축을 풀고 `GardenToolsGridy.exe`를 실행하세요. 배포 폴더 전체를 함께 보관하세요. `_internal` 폴더가 필요합니다. 사용자 PC에 Python을 별도로 설치할 필요가 없습니다.

1. JPG 또는 PNG 사진 2~3장을 창에 끌어 놓거나 **사진 추가**를 누릅니다.
2. 목록 드래그 또는 ↑·↓ 버튼으로 사진 순서를 바꿉니다.
3. 바깥 여백, 사진 사이 간격, 배경색을 조절합니다.
4. **전체 보이기**는 사진 전체를 유지합니다. **영역 채우기**는 가장자리를 잘라 각 행을 채웁니다.
5. 출력 크기와 JPG·PNG를 고르고 **이미지 저장**을 누릅니다.

기본값은 바깥 여백 40px, 간격 20px, 흰색, 전체 보이기, 1080×1350 JPG입니다. 1080×1440과 1080×1080도 선택할 수 있습니다. JPEG 품질은 95이며 PNG는 무손실입니다.

여백과 출력 옵션은 변경 시 `%LOCALAPPDATA%/GardenTools/Gridy/settings.json`에 자동 기록됩니다. **설정 초기화**를 누르면 기본값으로 돌아가며 이 값도 기록됩니다. 잘못 입력된 색상은 저장하지 않습니다.

## 저장 위치

원본과 같은 폴더에 `Gridy_날짜_시각_3장.jpg` 형식으로 저장합니다. 원본이나 기존 결과를 덮어쓰지 않으며, 같은 이름이 있으면 번호를 붙입니다. 다른 폴더의 사진을 섞은 경우 처음 추가된 사진의 폴더를 사용합니다. 순서를 바꿔도 저장 위치는 유지됩니다. 기준 사진을 제거하면 남아 있는 사진 중 가장 먼저 추가된 사진의 폴더가 기준이 됩니다.

저장 경로는 화면 하단에서 확인할 수 있습니다. 원본 폴더에 쓰기 권한이 없으면 파일을 다른 곳에 저장하지 않고 오류를 표시합니다. 원본이 이동되거나 변경되면 해당 사진을 제거하고 다시 추가하세요.

## 입력과 제한

- 파일당 최대 100MB, 최대 60MP. 정지 JPG·JPEG·PNG 지원.
- 드롭한 파일 중 오류가 있으면 그 묶음 전체를 추가하지 않습니다. 기존 사진은 유지합니다.
- 같은 경로의 파일은 중복 추가하지 않습니다. 4장 이상 합성과 여러 묶음 일괄 저장은 지원하지 않습니다.
- RGB·회색조·투명 이미지를 지원합니다. CMYK JPEG는 유효한 ICC 프로파일이 있어야 합니다.
- 사진 방향과 색상 프로파일을 반영합니다. 결과는 sRGB이며 원본 EXIF/GPS를 복사하지 않습니다.
- 전체 보이기에서는 사진 비율에 따라 행 안에 추가 여백이 생깁니다.
- 앱을 재실행하면 사진 목록은 비워지고, 여백과 출력 옵션은 마지막 유효 설정으로 복원됩니다. 인스타그램 자동 업로드는 제공하지 않습니다.
- 인스타그램 앱의 실제 업로드·표시 규격은 별도 확인이 필요합니다. 앱은 지정 크기의 파일을 생성합니다.

## 개발과 재실행

검증 환경은 Windows x64, Python 3.14.7입니다. 의존성은 프로젝트 전용 환경을 사용합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe main.py
```

uv를 쓰는 경우 `uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt`로 설치할 수 있습니다. 앱 실행 시 라이브러리를 자동 다운로드하지 않습니다.

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=artifacts/pytest-temp --junitxml=artifacts/pytest.xml
.venv/Scripts/python.exe main.py --smoke-test artifacts/source-smoke
.venv/Scripts/python.exe -m tools.benchmark
.venv/Scripts/python.exe tools/build.py
```

빌드는 `dist/버전-빌드시각/GardenToolsGridy/`와 버전·시각이 포함된 ZIP을 생성합니다. 기존 배포본은 유지합니다. 실행 파일의 Qt 통합 검사와 ZIP 무결성 검사가 통과하면 `Gridy.cmd`를 갱신합니다. 빌드 정보와 해시는 배포 폴더의 `build-info.json`, 검사 증거는 `artifacts/release-버전-빌드시각/`에 기록됩니다.

아이콘 원본은 `gridy/assets/app-icon.png`입니다. 정사각형 PNG를 바꾸고 다시 빌드하면 실행 파일과 앱 창에 적용됩니다. 버전 변경 시 `pyproject.toml`과 `gridy/__init__.py`를 함께 수정하고 `CHANGELOG.md`에 기록합니다. 빌드 시 두 버전이 일치하는지 확인합니다.

`--basetemp`는 pytest가 관리하고 실행 때 비우는 테스트 전용 폴더이므로 사용자 사진 폴더를 지정하지 마세요. `--smoke-test`는 지정 폴더에 테스트용 사진·결과·화면 PNG·JSON을 만듭니다. 실제 사용자 사진을 사용하지 않습니다.

## 수정 지점

| 파일 | 역할 |
| --- | --- |
| `gridy/config.py` | 기본값, 프리셋, 입력 한도 |
| `gridy/images.py` | 파일 검사, 방향·색상, 원본 변경 감지 |
| `gridy/layout.py` | 행 위치, 여백, 맞춤 계산 |
| `gridy/render.py` | 실제 이미지 합성 |
| `gridy/export.py` | 원본 폴더 저장, 충돌 방지, 재열기 검사 |
| `gridy/ui.py` | 화면, 드롭, 작업 스레드, 최신 미리보기 유지 |
| `tests/test_core.py` | 핵심 기능 자동 검사 |
| `gridy/smoke.py` | 소스·실행 파일 공통 Qt 통합 검사 |

진단 로그는 쓰기 가능한 경우 `%LOCALAPPDATA%/GardenTools/Gridy/gridy.log`에 저장합니다. 최대 1MB 로그 3개를 유지하며 파일을 외부로 전송하지 않습니다. 오류 로그에는 문제 파일의 로컬 경로가 포함될 수 있습니다.

