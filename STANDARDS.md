# 적용한 공통 규칙

- 표준: [Home Assistant Repository Standards](https://github.com/eigger/hass-repo-standards/tree/b54ac48102d6e326c6929071fdc02ba8fade794e)
- 참조 커밋 SHA: `b54ac48102d6e326c6929071fdc02ba8fade794e`
- 중앙 main 확인일: 2026-10-22.
- 최초 적용: 2026-10-18, [PR #114](https://github.com/eigger/hass-magic-caster-wand/pull/114). 이번 재검토: 2026-10-22, 기준 통합 `5e71012776658291d4aa88310d563520ee784a81` 이후 로컬 변경.
- profile: `integration / ha`; 실제 기본 브랜치: `master`; domain: `magic_caster_wand`; 테스트: `tests/components/magic_caster_wand/`.
- 조율: `root`; 구현: `standards_implementation`; 독립 리뷰·검증: `independent_review`.
- 적용·검증 근거: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md). 과거 실행과 이번 실행은 구분합니다.
- 중앙 현황: [원격 현황표](https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md). 이번 갱신은 별도 중앙 checkout의 로컬 기록이며 원격 게시 전입니다.

## 이번 적용과 사용자 영향

이전 검토 SHA `7acd9cab6ac774e4695f2c962e3d88b5faa4620d`에서 최신 공용 CI·README 관리 영역·테스트 기반·양언어 Bluetooth 문제 해결 계약으로 갱신합니다. 기존 사진·GIF·사용법·자동화 예제와 외부 전송 경계의 회귀 테스트를 보존합니다. 공용 workflow와 `standards-ref`를 같은 검토 SHA로 고정하고 Validate에 중앙 계약 검사를 추가합니다. 실제 HA 플랫폼별 입력·서비스·경계값 테스트 6개를 보완하고, strings.json의 Core 번역 참조를 기존 영어 배포 문자열과 같은 원문으로 해소합니다. 화면의 영어·한국어 문구와 런타임 동작은 변경하지 않습니다. 중앙 AGENTS.md를 이 저장소에 설치하지 않습니다.

HACS Default는 [공식 기본 통합 목록](https://github.com/hacs/default/blob/master/integration)의 `eigger/hass-magic-caster-wand` 등재를 2026-10-22 확인했습니다. 양언어 README의 Default 배지·공식 HACS Downloads 집계·My Home Assistant 설치 버튼과 기본 목록 다운로드 안내에 반영합니다. 설정 초기화나 기존 사용자 재등록은 필요하지 않습니다.

제품 분류는 `buttons_remotes`입니다. 실제 지팡이 제스처와 물리 버튼 입력으로 다른 HA 기기의 자동화를 제어하는 제품 용도에 근거하며, LED 효과·센서 플랫폼만으로 별도 제품 분류를 추정하지 않습니다. manifest의 `categories`는 배포 메타데이터입니다.

최소 HA `2025.4.0`, 통합 버전 `2.1.2`, 공개 domain·unique ID·config entry schema와 런타임 의존성은 유지합니다. current 검증 선언은 HA `2026.10.2` / Python `3.14` / pytest-homeassistant-custom-component `0.13.373`, 정확한 최소는 HA `2025.4.0` / Python `3.13` / plugin `0.13.232`입니다. blesession 최소 `0.9.0`/current 검증 축은 HA 최소/current와 별개입니다.

## 예외와 남은 검증

승인된 예외는 없습니다. 미실행·실패·미확인은 점검표에 그대로 기록하며 과거 PASS로 대체하지 않습니다. 원격 CI·기본 브랜치 게시·실물 검증은 해당 실행 근거가 생기기 전 완료로 표시하지 않습니다. 이번 변경의 commit/push·PR·tag/release는 수행하지 않습니다.

## 2026-10-23 다운로드 배지 부분 갱신

- 배지·DOC-03/05와 Validate 형식 검사기만 중앙 [`b54ac48102d6e326c6929071fdc02ba8fade794e`](https://github.com/eigger/hass-repo-standards/tree/b54ac48102d6e326c6929071fdc02ba8fade794e)를 채택합니다. 이전 기준 SHA `0ec31111a81b0ee5702f1d8a17f03616a10a5db6`의 채택 이력·예외는 보존합니다. 모든 중앙 workflow/action pin과 standards-ref는 GOV-02의 단일 기준 SHA 계약에 맞춰 갱신합니다. 중앙 diff에서 공용 workflow/action 실행 파일은 이전 기준과 동일함을 확인했습니다.
- 대상 기본 브랜치 커밋: `8cf723a523edfa2df425da40a62e87db2efbd1d9`. 주 에이전트 직접 구현·자체 리뷰(GOV-05의 배지/생성물 변경 범위), 검증은 [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md#2026-10-23-downloads-배지-부분-검증)에 기록합니다.
- Downloads는 모든 릴리스 첨부 asset 다운로드 합계입니다. 사용자 지시에 따라 ZIP 배포를 도입하지 않으며 현재 HACS 소스 파일 설치는 이 수치에 집계되지 않습니다. 통합 코드·의존성·지원 최소·기존 설치 안내는 변경하지 않습니다.
