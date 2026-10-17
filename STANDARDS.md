# 적용한 공통 규칙

- 표준: [Home Assistant Repository Standards](https://github.com/eigger/hass-repo-standards/tree/7acd9cab6ac774e4695f2c962e3d88b5faa4620d)
- 검토한 중앙 main 전체 SHA: `7acd9cab6ac774e4695f2c962e3d88b5faa4620d`
- 최초 적용일: 2026-10-18; 현재 상태: **이관 진행 중 (로컬 수정)**
- profile: `integration / ha` (실제 HA fixture·통합/플랫폼 로딩 검증)
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: [최신 main 현황](https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md)
- 조율: Codex root; 구현: `implementation`, `documentation`; 독립 리뷰·검증: `independent_review` (결과는 점검표).
- 중앙 현황: 조율 담당이 2026-10-18 중앙 checkout에 진행 중 등록; 원격 반영 여부는 최종 기록 확인.
- 실제 기본 브랜치: `master`; 기준 통합 커밋: `3f21b1b55c02bd7c00633aa12d420cf8d0bcee42` + 이번 미커밋 변경.
- domain / 테스트 경로: `magic_caster_wand` / `tests/components/magic_caster_wand/`
- 변경 전/후 지원 최소: HA `2025.4.0` (`hacs.json.homeassistant`); 통합 버전 `2.1.1` 유지. 지원 최소 상향 없음.
- current 검증 조합: HA `2026.10.2` / Python `3.14` / pytest-homeassistant-custom-component `0.13.373`.
- 정확한 최소 HA 검증 조합: HA `2025.4.0` / Python `3.13` / pytest-homeassistant-custom-component `0.13.232`.
- 라이브러리 검증 축: blesession 정확한 최소 `0.9.0` 및 current를 각 HA 환경과 분리해 검증. 실제 설치값·결과는 점검표에 기록.

## 적용 내용과 사용자 영향

공통 CI와 실제 HA 테스트 구조를 채택하고, 간결한 영어/한국어 README 및 상세 사용·Bluetooth·개발 문서를 분리합니다. 이전 README 본문은 [전체 사용 안내](docs/user-guide.md)에 보존합니다. 설정 초기화·재등록·버전 상향을 요구하는 문서 변경은 없습니다. 부분 setup 실패·취소의 BLE/플랫폼 정리, 다중 entry 해제 시 서비스 정리, 저장된 entry의 reauth 처리와 직접 사용하는 `bluetooth-sensor-state-data==1.7.5` 선언을 보완합니다. 공개 domain·unique ID·entry schema와 통합 버전은 유지합니다. 로그와 진단 속성은 민감 정보 노출을 줄이기 위해 원문 예외 대신 예외 클래스만 기록하고 장치/프록시 식별 정보·임의 backend metadata를 제거합니다. 구조화된 실패 단계·원인 키·신호/경로 개수·시간 정보는 유지합니다. 검증 결과는 점검표에서 확인합니다. 검토 SHA 갱신은 향후 명시적 채택 변경으로 진행하며 중앙 변경을 자동 상속하지 않습니다.

## 예외

현재 승인된 예외는 없습니다. 미충족·미검증은 예외로 간주하지 않고 점검표에 `TODO`로 기록합니다. 향후 예외가 필요하면 규칙 ID·이유·담당자·재검토 조건을 이곳에 기록합니다.

원격 CI, required checks 설정, 기본 브랜치 반영과 실물 검증을 수행하지 않은 상태를 완료로 표시하지 않습니다. 2026-10-18 사용자 후속 지시로 채택 PR·CI 확인·스쿼시 머지를 진행합니다. tag/release는 생성하지 않습니다.
