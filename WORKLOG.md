# Gridy 구현 기록

2026-10-09: 명세서에 따라 첫 버전 구현 시작. 기존 파일은 작업명세서뿐이며 Git 저장소는 없다.

- 기술: Python 3.14.7, PySide6 Essentials 6.12.0, Pillow 12.3.0. 프로젝트 `.venv`에 설치.
- 원본 제작 지침 경로 접근 불가로 지정된 로컬 사본 및 technical-art-agents.md 적용.
- 완료 기준: 명세서 A01~A16을 해당 범위에서 검사하고 증거 기록. A17 실제 Instagram 업로드는 별도 사용자 계정 게시 행위이므로 이번 구현에서 실행하지 않는다.
- 구현 완료: 합성, 입력, 원본 검사, 저장, Windows UI, 비동기 미리보기, 원본/이전 결과를 덮어쓰지 않는 저장 방식.
- 검사: 33개 핵심 테스트 PASS, 소스와 실행 파일 각각 16개 Qt 통합 체크 PASS, 실제 Windows 파일 선택·저장 PASS.
- 시각 검사로 선택 썸네일의 Qt 강조색 적용 발견 후 수정. OFFSCREEN 폰트 로딩도 보완.
- 최초 패키징에서 호스트 PATH의 Poppler ICU DLL이 잘못 수집되어 실행 실패. 빌드 PATH를 Python과 Windows로 제한하고 clean build 후 frozen smoke PASS.
- pytest 기본 임시 폴더가 샌드박스에서 거부되어 작업 폴더 내부 전용 basetemp로 변경하여 검사 완료.
- 성능 및 제한: `검증결과.md`와 artifacts의 JSON/XML/PNG 참조. A17 게시, 16GB PC와 다른 깨끗한 PC 실행은 NOT_RUN.
- 재개: README에 개발 실행·테스트·빌드 명령 기록. 배포 폴더는 `dist/GardenToolsGridy`.

## 2026-10-09 — 1.0.1 아이콘 및 버전 기록

- 사용자 제공 `그라데이션 콜라주 사진 아이콘.png`를 `gridy/assets/app-icon.png`에 원본 그대로 복사. 원본·사본 SHA-256 일치 확인. 배경과 구도 유지.
- 실행 파일 ICO 7개 크기(16/24/32/48/64/128/256px), Qt 창·앱 아이콘 적용. 앱 및 프로젝트 버전 1.0.1, CHANGELOG와 Windows 파일·제품 버전 기록.
- 빌드 도구는 기존 배포본을 유지하며 버전·시각별 폴더, ZIP, SHA-256, build-info.json을 생성. frozen smoke와 ZIP CRC 검사가 통과한 뒤 Gridy.cmd 갱신.
- 최종 배포: `dist/1.0.1-20261009-102117-853757/GardenToolsGridy/GardenToolsGridy.exe`.
- PASS: 핵심 테스트 33개, 새 실행 파일 Qt 통합 검사 16개, 저장 결과 재열기, ZIP CRC 검사.
- PASS: EXE 리소스에서 추출한 7개 아이콘 데이터와 생성 ICO가 바이트 단위로 일치. Windows FileVersion/ProductVersion 모두 1.0.1. 배포 PNG와 사용자 원본 일치. 실행 파일 해시 및 런처 경로 일치.
- 시각 확인: EXE에서 추출한 256px 아이콘과 frozen UI 캡처에서 첨부 이미지 적용 확인.
- 증거: `artifacts/pytest-1.0.1.xml`, `artifacts/build-1.0.1.log`, `artifacts/release-1.0.1-20261009-102117-853757/`의 smoke.json·icon-verification.json·PNG.
- 기존 1.0.0 실행 파일·ZIP 및 실행 중인 앱은 보존. 별도 PC·실제 Instagram 업로드 등 이전 미실행 항목은 그대로이며 이번 변경에서 재검사하지 않음.

## 2026-10-11 — 1.0.2 여백과 출력 설정 기억

- 바깥 여백, 간격, 배경색, 맞춤, 크기, 형식을 변경할 때 마지막 유효 옵션을 사용자 로컬 settings.json에 원자적으로 저장하고 시작 시 복원. 초기화도 저장하며 사진 목록은 보존하지 않음.
- gridy/preferences.py로 파일 저장·복원 분리. 잘못된 설정은 기본값으로 복구하고 저장 실패는 UI 및 로그 안내. 자동 검사에서는 별도 설정 경로 사용.
- PASS: pytest 44개(별도 앱 프로세스 재실행, 잘못된 파일, 쓰기 실패 시 기존 파일 보존 포함), 배포 EXE Qt 통합 검사 19개, 출력 이미지 재열기, ZIP CRC 검사. 배포 UI 캡처 직접 열어 확인.
- 배포: dist/1.0.2-20261011-155143-696519/GardenToolsGridy/GardenToolsGridy.exe. Gridy.cmd를 새 빌드로 갱신. 기존 배포본 및 실행 중 사용자 앱은 보존.
- 증거: artifacts/pytest-1.0.2.xml, artifacts/build-1.0.2.log, artifacts/release-1.0.2-20261011-155143-696519/.
- 제한: Qt 통합 검사는 offscreen 실행. 실제 사용자 설정 파일을 변경하는 검사 및 별도 PC 검사는 실행하지 않음.

## 2026-10-11 — 1.0.3 버전 증가 및 재빌드

- 사용자 요청에 따라 앱·프로젝트 버전 1.0.2 → 1.0.3, README 및 CHANGELOG 갱신. 기능 코드는 변경하지 않음.
- PASS: 새 배포 EXE Qt 통합 검사 19개, ZIP CRC, Windows FileVersion/ProductVersion 1.0.3, Gridy.cmd의 새 실행 파일 연결.
- 배포: dist/1.0.3-20261011-155416-995019/GardenToolsGridy/GardenToolsGridy.exe 및 같은 빌드 ID의 win64 ZIP.
- 증거: artifacts/build-1.0.3.log 및 artifacts/release-1.0.3-20261011-155416-995019/smoke.json.
- 기능 코드 변경이 없어 pytest 재실행은 생략. 별도 PC 실행 미검증. 기존 배포본 보존.
