# 공통 규칙 적용 체크리스트

이 기록은 2026-10-18 로컬 적용 작업의 진행 상태입니다. 구현 및 독립 검증 결과가 기록되기 전에는 채택 완료를 뜻하지 않습니다. [사용법과 판정 기준](https://github.com/eigger/hass-repo-standards/blob/7acd9cab6ac774e4695f2c962e3d88b5faa4620d/docs/checklist.md)을 읽고, 아래 규칙은 `STANDARDS.md`에 기록한 표준 커밋에서 확인합니다. 표준은 태그·릴리스 대신 검토한 `main` 커밋 SHA로 고정합니다.

## 검토 대상

| 항목 | 값 |
|---|---|
| 통합 리포 / 실제 기본 브랜치 | `eigger/hass-magic-caster-wand` / `master` — GitHub API 확인 |
| domain / 구현 경로 | `magic_caster_wand` / `custom_components/magic_caster_wand/` |
| 검토 대상 통합 커밋 / 채택 PR | 기준 `3f21b1b55c02bd7c00633aa12d420cf8d0bcee42` + 이번 미커밋 작업 / PR 없음 |
| 검토한 표준 전체 커밋 SHA | `7acd9cab6ac774e4695f2c962e3d88b5faa4620d` |
| 검토일 / 조율 담당 | 2026-10-18 / Codex root |
| 구현 서브 에이전트 / 독립 리뷰·검증 서브 에이전트 | `implementation`, `documentation` / `independent_review` |
| 중앙 현황표 반영일 / 기록 | 2026-10-18 조율 담당이 중앙 checkout에 진행 중 등록; 원격 반영은 별도 확인 필요 |
| 변경 전 지원 최소 HA / 근거 파일(hacs.json·manifest·README) | `hacs.json.homeassistant = 2025.4.0`; manifest/이전 README에 별도 HA 하한 없음; 통합 버전 `2.1.1` |
| 유지·변경할 지원 최소 / 변경 시 실제 비호환 근거·명시적 승인 | 기존 `2025.4.0` 유지; 최소 상향 없음 |
| current 테스트 HA / 호환 Python·플러그인 | HA `2026.10.2`, Python `3.14.5`, 플러그인 `0.13.373`; 독립 설치·검증은 아래 기록 |
| 최소 테스트 HA / 호환 Python·플러그인 | HA `2025.4.0`, Python `3.13.14`, 플러그인 `0.13.232`; 별도 환경, 아래 기록 |
| profile / 테스트 경로 | `integration / ha` / `tests/components/magic_caster_wand/` |
| 이전 검토 기록 | 최초 공통 규칙 채택 |
| 채택 판정 | 이관 진행 중 — 로컬 수정·독립 검증·원격 CI/기본 브랜치 반영 확인 전 |

상태: `TODO` = 미확인·미충족, `PASS` = 근거로 확인, `EXCEPTION` = 적용 대상의 기록된 예외, `N/A` = 적용 조건에 해당 없음. 모든 항목은 미확인으로 시작합니다. `TODO`를 해당 없음으로 처리하지 않습니다. 묶은 규칙의 결과가 다르면 행을 나눕니다. 권장 항목은 별도로 표시했으며 미채택 이유를 기록합니다.

## 채택·구조·사용자 데이터

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| GOV-01, GOV-02 | `STANDARDS.md`에 표준 SHA·profile·실제 기본 브랜치·예외 기록, workflow/action은 검토 SHA로 고정 | PASS | `STANDARDS.md` 전체 SHA·profile·기존 최소 기록; 공통 workflow 3개 모두 실제 검토 SHA 고정. |
| GOV-03 | 새 표준 채택 변경의 영향·이관 방법과 명시적 채택 PR 확인. 규칙 자체를 변경하면 공통 CHANGELOG 기록 | TODO | 적용 영향·이관 방법은 STANDARDS/CONTRIBUTING에 기록. 로컬 변경이며 채택 PR/기본 브랜치 반영은 미실행. 중앙 규칙 자체 변경 없음. |
| GOV-04 | 중앙 표에 작업 시작·단계 변경·종료 상태, 담당·적용 내용·검증/리뷰 근거·남은 작업 갱신, 타 리포 기록 보존 | TODO | 중앙 checkout의 자기 행만 진행 중 등록, 기존 타 행 수정 보존. 원격 반영 미실행; 종료 시 로컬 검증 결과 갱신. |
| GOV-05 | 구현과 독립 리뷰·검증을 별도 서브 에이전트에게 위임, 지적 수정·재검증 및 결과 취합 | PASS | implementation/documentation 구현, 별도 independent_review 리뷰. 부분 setup cleanup·다중 entry stale runtime·진단/로그 비식별화·개발 명령 지적 수정, 최종 4matrix 각274passed 재검증. 아래 고정 tree 해시/로그 기록. |
| HA-01, HA-13 | `custom_components/<domain>/`와 domain 일치, 필요한 모듈·공개 API·생명주기는 Core 대응 구조 | PASS | 기존 domain·배포 경로 유지; runtime_data/config_flow/device_setup/플랫폼·프로토콜 경계와 실제 HA loader 검증. |
| HA-02 | manifest 필드·정렬·동작 선언 확인, 공식 품질 등급 자가 표기 없음 | PASS | manifest domain/name 이후 알파벳순, 실제 Bluetooth discovery/dependencies·local_polling 선언, 자가 품질 등급 없음. |
| HA-03 (권장) | 공통 상수·설정·갱신·플랫폼 역할 및 프로토콜 경계에 맞게 모듈 구성 | PASS | const/config_flow/runtime_data/device_setup와 플랫폼·mcw_ble/mcb_ble/common_ble 역할 분리 유지. |
| HA-04, HA-08 | UI 설정·중복·안정적 식별 및 기능별 options/reauth/reconfigure, entity 의미·registry 영향 확인 | PASS | test_config_flow.py 실제 user/Bluetooth/중복/미지원/reauth/options, test_init.py wand/box registry·state·action 검증. |
| HA-01, HA-04, HA-08, REL-01, REL-03 | domain·unique ID·entry schema·상태/통계 계약 변경 시 migration 테스트와 사용자 조치 안내 | N/A | 이번 변경은 공개 domain·unique ID·entry VERSION/schema·상태/통계 계약을 변경하지 않음. 기존 upgrade 회귀 유지. |
| HA-05, HA-06 | setup 실패 구분, unload/reload·부분 실패의 task/listener/연결 정리, async·timeout·취소 처리 | PASS | test_init.py entry setup/unload/reload·부분 setup 실패/취소·unload 거절·다중 entry 서비스 정리; 기존 detector/tracking 취소 회귀 유지, 공유 HA HTTP session 및 명시 timeout 사용. |
| HA-07 | 중복 polling·property I/O 방지, push 보존, unavailable/unknown·실패 후 복구 | PASS | 기존 coordinator/push 경계 유지; test_init·lifecycle·spell_tracking_reconnect의 상태/실패/복구 회귀. |
| HA-11, HA-12 | 번역·action/schema 일치, 로그/diagnostics/fixture 비식별화와 제공 시 redaction 테스트 | PASS | action/schema·번역 계약 유지. BLE/HTTP 주소·serial·alias·raw packet/예외/metadata 로그 제거 및 diagnostics allowlist, test_privacy/test_session_diagnostics로 비식별화 검증; 독립 최종 sweep 통과. |

## 실제 HA 테스트·호환성·의존성

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| TEST-08 | `tests/components/<domain>/`에 구현과 대응하는 테스트·domain fixture 배치, discovery·CI 경로 일치 | PASS | tests/components/magic_caster_wand/ 이동; tests 및 components/domain __init__, 실제 fixture와 pytest testpaths/CI 경로 일치. |
| TEST-02, TEST-03, DEP-07 | 실제 HA·호환 플러그인과 `hass`/`enable_custom_integrations` fixture 사용, HA core stub/복사본/`--no-deps`로 대체하지 않음 | PASS | 실제 HA/plugin/hass/enable_custom_integrations 사용; 기존 sys.modules HA/외부 library stub 제거, --no-deps 사용 없음. |
| TEST-09 | 실제 loader·config entry manager로 setup/플랫폼 로딩, HA 상태·registry·service/action으로 결과 검증 | PASS | test_init.py 실제 config entry manager setup/forward/unload/reload, 7개 wand 플랫폼 registry/state와 service action; box setup 검증. |
| TEST-01, TEST-06, TEST-07 | 구현 기능별 성공·실패·중복·migration·unload·복구 회귀 검증, 외부 통신 경계만 mock, skip 사유 | PASS | 기존 169 test 함수 보존; mock Bluetooth transport와 HTTP 경계, 실제 HA fixture/registry/service 테스트 추가. 실패/중복/취소/복구·서비스 정리 회귀 포함. |
| TEST-04, HACS-01 | 변경 전 지원 최소·current·각 Python/플러그인 분리, 선언한 정확한 최소 검증, 상향 시 비호환 근거·명시적 승인 확인 | PASS | hacs.json HA2025.4.0·통합2.1.1 유지. 실제 정확한 최소/현재 HA별 호환 Python/plugin 분리 설치·실행. |
| TEST-05, HA-10, DEP-02, DEP-05 | imagespec·blesession 등 최소/현재 라이브러리 별도 환경, 실제 HA 테스트·정확한 설치값·API 경계 검증 | PASS | 양 HA current/minimum 모드 독립 resolver·pipcheck·실제HA테스트 각274passed. blesession 실제0.9.0 양mode (current도 현재 선택값 동일); sensor-state-data1.7.5 고정, 공개 session API 회귀 유지. |
| DEP-01, DEP-06 | Python runtime은 manifest requirements, HA domain은 dependencies/after_dependencies, 테스트·린트 requirements는 별도 | PASS | 기존 직접 import하던 미선언 bluetooth-sensor-state-data==1.7.5를 manifest 추가. 런타임 numpy/blesession은 manifest, HA domain dependencies와 test/lint requirements 분리. |
| DEP-07, CI-06 | 실제 사용하는 HA 구성요소의 requirements·필수 재귀 의존성·선택 로딩 경로 설치, resolver·`pip check` 통과 | PASS | 고정한 중앙 install.py로 manifest+test resolver, 설치한 HA의 bluetooth_adapters/camera 재귀 requirements 설치, 양 HA pip check clean. |
| DEP-02, DEP-03, DEP-08 | 의존성 추가/변경의 버전·extras·marker·선언 위치·지원 플랫폼·라이선스 검토, 실제 HA 테스트와 문서 갱신 | PASS | 외부 직접 패키지1.7.5 고정은 양 HA resolver/실제 테스트 통과; 기존 numpy 무버전 및 blesession>=0.9.0 유지. 기존 import의 누락 선언 보완, extras/marker 변경 없음. |

독립 리뷰는 변경 전후 지원 최소와 current를 비교하고, 봇 PR이 과거 최소 requirements·constraints까지 갱신하거나 expected-ha-version·Python을 누락하지 않았는지 확인합니다. 최신 테스트 실패는 호환 수정 대상으로 처리합니다.

환경마다 아래 행을 복사합니다. 최소 HA와 최소 라이브러리 검증을 혼동하지 않고, marker가 활성인 환경에서 대상 패키지 설치값을 확인합니다. 실행하지 않은 조합은 `TODO` 또는 근거가 있는 `EXCEPTION`으로 남깁니다.

| 검증 축 / 상태 | 통합 커밋 | Python / HA / 플러그인 실제 버전 | 대상 패키지 실제 버전·extras·marker | 명령·테스트 결과·pip check / CI run·job | skip·제외·미검증 범위 |
|---|---|---|---|---|---|
| current HA / current deps / PASS | 기준 `3f21b1b` + 미커밋 구현 (최종 독립 검증 기록 참조) | Python `3.14.5` / HA `2026.10.2` / plugin `0.13.373` | blesession `0.9.0`, bluetooth-sensor-state-data `1.7.5`, numpy `2.3.2` | 중앙 install.py current·pip check clean; 독립 pytest `274 passed` | skip 0; 실물/HA UI/원격 CI 미검증 |
| current HA / minimum deps / PASS | 동일 로컬 구현 | Python `3.14.5` / HA `2026.10.2` / plugin `0.13.373` | blesession 정확한 하한 `0.9.0`, sensor-state-data `1.7.5`, numpy `2.3.2` | 중앙 install.py minimum·pip check clean; 독립 pytest `274 passed` | skip 0; current와 같은 선택 버전이지만 별도 resolver/mode 실행 |
| 정확한 최소 HA / current deps / PASS | 동일 로컬 구현 | Python `3.13.14` / HA `2025.4.0` / plugin `0.13.232` | blesession `0.9.0`, sensor-state-data `1.7.5`, numpy `2.2.2` | 중앙 install.py current·pip check clean; 독립 pytest `274 passed` | skip 0; macOS asyncinotify/inotify upstream 경고 1개 |
| 정확한 최소 HA / minimum deps / PASS | 동일 로컬 구현 | Python `3.13.14` / HA `2025.4.0` / plugin `0.13.232` | blesession 정확한 하한 `0.9.0`, sensor-state-data `1.7.5`, numpy `2.2.2` | 중앙 install.py minimum·pip check clean; 독립 pytest `274 passed` | skip 0; macOS upstream 경고 1개; 실물/HA UI/원격 CI 미검증 |

## HACS·CI·의존성 업데이트

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| HACS-01, HACS-02 | 루트 README/LICENSE/hacs.json, 검증한 최소 HA, 실제 배포 구조와 필요한 옵션 일치 | PASS | 루트 hacs.json/README/LICENSE와 custom_components/magic_caster_wand 배포 유지, 최소 HA2025.4.0 별도 실제 검증. |
| HACS-03, HACS-05 | Default 여부는 목록 근거로 확인, [로컬 brand/icon.png 또는 원격 brands 근거](https://github.com/eigger/hass-repo-standards/blob/7acd9cab6ac774e4695f2c962e3d88b5faa4620d/docs/hacs.md)와 HACS/Hassfest 실제 실행, ignore는 이유·해제 조건 기록 | TODO | Custom 배지·로컬 brand/icon.png 존재. 이번 미커밋 tree HACS/Hassfest 원격 실행 미실행; ignore 없음, reusable Validate caller 준비. |
| HACS-06 (권장) | description·topics·issue 경로·brands 및 사용하는 HACS 필드 지원 확인 | PASS | GitHub API default master·Issues/Discussions·release2.1.1 확인. 기존 local brand assets 유지; 오래된 HACS 필드 없음. |
| CI-01, CI-02 | Validate/Python Tests 공통화, 확장 job 유지, PR·실제 기본 브랜치 push·dispatch 및 필요한 schedule | PASS | Tests·Validate 공통 reusable workflow; master push/PR/dispatch, Validate 및 updater 분산 schedule. |
| CI-03, CI-05, CI-08 | 최소 권한·checkout 자격증명 비보존·timeout·concurrency, full SHA·갱신 관리, 비신뢰 입력·secrets 경계 | PASS | 읽기 검증·쓰기 updater 분리, SHA고정·중앙 checkout 자격증명 비보존/timeout, concurrency·Dependabot, 비신뢰 shell 입력/secrets inherit 없음. actionlint 통과. |
| CI-04, CI-07, CI-12 | 실패를 숨기지 않는 실제 `ha` 필수 테스트, 버전별 환경·cache·Ruff 설정과 required checks 이름 확인 | TODO | current/minHA 각각 current/minimum 의존성 4matrix·필수 실제 ha profile와 lint 병렬 구성. 원격 CI/required checks 새 job명 설정은 미확인; 로컬 실패 숨김 없음. |
| DEP-03, DEP-04, CI-09 | updater의 선택 package·연산자/extras/marker 보존, 안정 버전·major 정책, 실제 기본 브랜치·단일 bot branch·PR만 제안 | PASS | 공통 updater blesession만 선택·단일 bot branch·안정 버전/major정책 사용. dry-run Requirements are current; no change. manifest 변경 없음. |
| CI-09, CI-10, DEP-08 | 변경 tree의 새 하한·실제 HA 검증 후 PR 동기화, 실패 시 중단·변경 없음 시 기존 PR 정리, 후속 required checks 충족 방식 확인 | TODO | 변경tree 실제 HA 검증 명령·실패 중단은 고정한 공통 구현 사용. GITHUB_TOKEN PR 후속 CI 자동 실행 가정 없음. 실제 botPR/dispatch·required check 운영은 미실행. |

## README·Bluetooth·유지보수

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| DOC-01, DOC-02, DOC-06 | 영어 README.md·한국어 README.ko.md·상호 링크·기존 내용 보존, 간결한 제목/소개/핵심지원/최소요구/빠른설치·설정/짧은예제/중요제한/문서목록, 상세옵션·긴YAML·참조·개발/실HA테스트·의존성/검증범위를 docs·examples 등으로 보존·분리하고 유효한 링크 제공, 실제 활성 Issues·Discussions 또는 대체 지원 경로·실제 LICENSE 링크 | PASS | 이중 언어 간결 README·언어링크, 긴 기존 본문 docs/user-guide 보존, setup/troubleshooting/CONTRIBUTING 분리. 실제 활성 Issues/Discussions·LICENSE 확인, 로컬 링크 검사 통과. |
| DOC-03, DOC-04, DOC-05 | 제목 아래 관리 블록, flat-square·순서·실제 조건별 배지, CI 실제 기본 브랜치, 필수 동적 Usage·Analytics 참여 설치 의미·미집계/조회 실패와 0 설치 구분·이전 안내 보존 | PASS | 관리 블록·flat-square 순서·master CI·HA2025.4.0·release2.1.1·동적 domain Usage, opt-in/미집계!=0 설명. sync_badges --check 통과. |
| HA-09, HA-10 | BLE 사용 시 HA Bluetooth API·라이브러리 공개 경계, 지원한 proxy 경로·재연결·취소·서비스 변경 검증 | PASS | HA Bluetooth/blesession 공개 경계 유지; disconnect/reconnect/service 변경/notification 취소 회귀, 프록시 실물 미검증은 별도 기록. |
| DOC-07 | blesession/proxy 통합 README의 핵심조건·상세문서 링크, 공통 Bluetooth 설정·추천기기·active 스캔/GATT 차이, 통합별 troubleshooting 또는 공통 링크+모델고유조건·실제진단·민감정보 제거 제보 안내 | PASS | 공통 Bluetooth 설정/추천보드 링크, discovery와 GATT·두 active 구분, 장치별 전원/타앱/인증/모델제약·troubleshooting·실제 진단 경로. |
| DOC-07, HA-12 | 기기별 깨우기·인증·타 앱 연결·전송 제약, 실제 검증 경로와 미검증 범위, 공개 문제 로그 비식별화 | PASS | docs/setup 및 troubleshooting의 장치 준비·모델별 제약·진단 entity·제보 redaction, 실물 경로 미검증 명시. 가짜 diagnostics 다운로드/옵션 없음. |
| HACS-04, REL-01, REL-02, REL-03, CI-11 | 통합 릴리스 시 같은 검증 commit/tag·manifest 버전·산출물·권한, 사용자 영향·지원 변경·제한 안내 | N/A | 통합2.1.1 유지, 새 tag/release/산출물 배포 없음. CONTRIBUTING 릴리스 별도 검증·버전일치·사용자 영향 절차 기록. |
| REL-04 | 이전/중단 시 README 상단 경로·유지보수 상태·재등록 여부, 자동 이전으로 오인하지 않는 안내 | N/A | 리포 이전·통합·중단 작업 아님. |
| REL-05 (권장) | 의존성/HA API 변경과 기능 변경 분리, 표준 변경은 명시적 채택 PR로 반영 | PASS | 이번 작업은 표준 채택·호환성/생명주기/개인정보 보완. 새 사용자 기능이나 지원 최소 변경 없음; 원격 채택은 후속 검증 필요. |

## 예외와 남은 작업

현재 로컬 구현의 승인된 예외는 없습니다. 원격/운영 검증 미실행은 예외나 PASS로 바꾸지 않고 다음 TODO로 남깁니다.

| 규칙 ID / TODO | 남은 작업 | 담당자 | 완료 조건 |
|---|---|---|---|
| GOV-03, GOV-04 | 로컬 변경을 기본 브랜치에 반영한 뒤 중앙 현황의 해당 행 원격 갱신 | 저장소 관리자 / Codex root | 실제 반영 SHA·CI 링크 확인; 현재 중앙 checkout에만 기록 |
| HACS-05, CI-04/07/12 | 이번 tree의 HACS/Hassfest 및 원격 Tests4matrix 실행; required checks 이름 검토 | 저장소 관리자 | 새 reusable workflow job 이름에 맞는 보호설정·실제 run 성공 |
| CI-09/10 | 실제 botPR 생성·후속 required check 운영 확인 | 저장소 관리자 | dry-run과 실제 writePR 실행 구분; GITHUB_TOKEN 후속 실행 제약 확인 |

실물 wand/box·펌웨어·로컬 어댑터/프록시·HA UI는 이번 작업에서 확인하지 않았습니다. 이는 로컬 실제 HA+mock BLE 테스트와 별개이며 실물 성공을 주장하지 않습니다. 통합 버전·지원 최소·공개 unique ID/schema는 유지합니다.

중앙 상태는 `진행 중`으로 유지합니다. 기본 브랜치 반영·원격 검증 전에는 완료 판정하지 않습니다. 이전 로컬 구현 검증 시점에는 commit/push/PR을 생성하지 않았으며, 2026-10-18 사용자 후속 지시로 PR·CI 확인·스쿼시 머지를 진행합니다. tag/release는 생성하지 않습니다. 중앙 표도 자기 행의 로컬 변경만 했으며 원격 반영은 미실행입니다.

## 문서 구현 근거

- `README.md`와 `README.ko.md`: 간결한 이중 언어 시작 안내, 기존 HA 2025.4.0 하한, 관리 배지와 실제 domain Usage 유지.
- 기존 README 전체는 `docs/user-guide.md`로 보존; `docs/setup.md`, `docs/troubleshooting.md`, `CONTRIBUTING.md` 추가.
- GitHub API: 기본 브랜치 `master`, Issues/Discussions 활성, 최신 정식 release `2.1.1` 확인.
- `.hass-standards.json`에 확인한 저장소/기본 브랜치·두 README·설치 앵커 설정.
- `python3 /Volumes/HDD/GitHub/hass-repo-standards/scripts/sync_badges.py /Volumes/HDD/GitHub/hass-magic-caster-wand --write`: 성공.
- 원격 CI·required checks·실물 BLE 조합 검증은 미실행. 독립 검증은 아래 해당 tree의 실제 기록이며 과거 결과를 PASS로 재사용하지 않음.

## 최종 독립 검증 근거 — 2026-10-18

- 구현 담당 `implementation`, 문서 담당 `documentation`, 독립 리뷰·검증 `independent_review`; 주 에이전트 `root`가 결과를 통합했습니다.
- 기준 통합 `3f21b1b55c02bd7c00633aa12d420cf8d0bcee42` + 이번 미커밋 tree. 독립 검사한 runtime/tests/CI/config 78파일 해시 목록: `/tmp/mcw-independent-final-hashes.json`; 목록 SHA256 `e709accdfb118278ae5a66f6d32f7d1634253d8cb6305c6b805c2bbca7dcf29f`. 최종 실행 전후 해당 파일 변경 없음(`changed []`). 이 목록은 최종 문서 갱신을 포함하지 않는 구현 검증 기준입니다.
- 분리 환경에서 고정 SHA의 `actions/python-environment/install.py`를 `INPUT_DOMAIN=magic_caster_wand`, `INPUT_REQUIREMENTS=requirements_test.txt` 또는 `requirements_test_min.txt`, `INPUT_DEPENDENCY_MODE=current`/`minimum`, `INPUT_MINIMUM_PACKAGES='["blesession"]'`, `INPUT_HA_COMPONENTS='bluetooth_adapters camera'`, `INPUT_EXPECTED_HA_VERSION=2026.10.2` 또는 `2025.4.0`, `INPUT_TEST_PROFILE=ha`로 실행. 정확한 재현 명령과 RUNNER_TEMP 준비는 CONTRIBUTING 참조.
- 각 조합에서 `python -m pytest tests/components/magic_caster_wand/ -q`, `python -m pip check`: **274 passed, skip 0**, 의존성 충돌 없음. current Python3.14.5/pytest9.0.3/pytest-asyncio1.4.0; minimum Python3.13.14/pytest8.3.5/pytest-asyncio0.26.0. 최소 HA의 경고1개는 macOS에서 Linux inotify를 제공하지 않는 upstream asyncinotify 경고이며 테스트 실패/skip 아님.
- 상세 독립 로그: `/tmp/mcw-independent-final-{current,min}-{current,minimum}-{install,pytest}.log`. 임시 파일은 재부팅/정리 시 소실될 수 있어 실제 버전·명령·결과를 이 문서에도 보존합니다.
- 구현 담당 별도 환경 `/tmp/mcw-implementation-current`, `/tmp/mcw-implementation-min`에서도 각274passed 및 4mode resolver/pipcheck 성공. 양 환경 blesession0.9.0, bluetooth-sensor-state-data1.7.5; 현재 numpy2.3.2/bleak3.0.2/habluetooth7.1.2, 최소 numpy2.2.2/bleak0.22.3/habluetooth3.37.0. 새 직접 패키지1.7.5 메타데이터: Apache2.0, Python>=3.9, OS Independent.
- 기존 169개 test 함수 이름 전량 보존; 가짜 HA core 모듈 제거, link/services를 실제 HA registry/service fixture로 전환. 새 entry/플랫폼/state/action·설정/options·실패·취소·개인정보 회귀 추가.
- `python -m ruff check .`, `python -m ruff format --check .`: Ruff0.17.1 PASS, 67files. `actionlint`1.7.12 모든 caller PASS, `git diff --check` PASS, 관리 배지 검사 PASS, 문서8개 로컬 파일 링크 검사 PASS.
- 중앙 `scripts/check_repository.py`: 25docs/7workflows/JSON/caller 계약 PASS (중앙 checkout 검사이며 통합의 원격 HACS/Hassfest 대체 아님); 중앙 `python -m unittest discover -s tests -v`:22passed.
- `python actions/update-manifest/update.py --manifest <통합 manifest> --packages '["blesession"]'`: dry-run PASS, `Requirements are current; no change`, manifest 변경 없음.
- 주요 독립 지적: 다중 entry 해제 후 stale runtime_data로 서비스 잔류, 플랫폼 로딩 후 setup 실패 정리, diagnostics 오류 원문/route 식별값·장치/HTTP/alias/macro 로그 노출, 로컬 installer RUNNER_TEMP 누락. 수정 후 관련 회귀와 최종4matrix 재검증을 통과했습니다. 남은 필수 구현 지적 없음.
- 원격 push/PR/Actions/HACS/Hassfest·branch protection·실물 BLE/HA UI 미실행. 중앙 원격 표도 미반영이며 중앙 checkout의 자기 행만 결과 갱신했습니다. 상태는 `진행 중`입니다.
