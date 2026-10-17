# Magic Caster Wand

<!-- hass-standards:badges:start -->
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](#설치)
[![Release](https://img.shields.io/github/v/release/eigger/hass-magic-caster-wand?style=flat-square)](https://github.com/eigger/hass-magic-caster-wand/releases)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.4.0-41BDF5?style=flat-square)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/tests.yml?branch=master&style=flat-square&label=Tests)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/validate.yml?branch=master&style=flat-square&label=Validate)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-magic-caster-wand?style=flat-square)](LICENSE)
[![Analytics reporting installs](https://img.shields.io/badge/dynamic/json?style=flat-square&color=41BDF5&label=Usage&query=%24.magic_caster_wand.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)](https://analytics.home-assistant.io/)
<!-- hass-standards:badges:end -->

[English](README.md) | **한국어**

해리 포터 Magic Caster Wand와 보관함을 Bluetooth로 Home Assistant에 연결하는 HACS 커스텀 통합입니다. 주문과 버튼으로 자동화를 실행하고, LED·진동을 제어하며 지팡이 움직임을 시각화합니다.

## 지원 기기와 최소 요구사항

- 지팡이 모델: **Defiant, Loyal, Honourable**. Magic Caster Box도 지원합니다.
- Home Assistant **2025.4.0 이상**, HACS 또는 수동 설치, 연결 가능한 Bluetooth 어댑터 또는 ESPHome Bluetooth proxy가 필요합니다.
- 기기를 충전하고 깨운 뒤 Bluetooth 범위 안에 둡니다. 프록시는 `bluetooth_proxy.active: true`가 필요합니다. [공통 Bluetooth 설정·추천 기기](https://github.com/eigger/hass-repo-standards/blob/main/docs/bluetooth.md)를 확인하세요.

## 설치

1. HACS에서 `https://github.com/eigger/hass-magic-caster-wand`를 **Integration** 유형의 사용자 지정 저장소로 추가하고 **Magic Caster Wand**를 다운로드합니다. 수동 설치 시 `custom_components/magic_caster_wand` 폴더만 HA 설정 폴더의 `custom_components` 안에 복사합니다.
2. Home Assistant를 재시작합니다. **설정 → 기기 및 서비스 → 통합 구성요소 추가 → Magic Caster Wand**를 선택하거나 Bluetooth 발견 알림을 확인합니다.
3. 깨어 있는 지팡이 또는 보관함을 선택하고 **Connect** 스위치를 켭니다. 주문 수신·명령 전송 전에 연결이 필요합니다. 움직임 시각화에는 지팡이의 **Spell Tracking**을 켭니다.

TFLite URL, 주문 초기화 시간과 연결 상세는 [설정 안내(영어)](docs/setup.md)를 참고하세요.

## 대표 예제

엔티티 ID를 실제 값으로 바꾸세요. `last_updated` 속성으로 트리거하면 같은 주문의 반복 시전도 처리합니다.

```yaml
triggers:
  - trigger: state
    entity_id: sensor.mcw_example_spell
    attribute: last_updated
conditions:
  - condition: state
    entity_id: sensor.mcw_example_spell
    state: Lumos
actions:
  - action: light.turn_on
    target:
      entity_id: light.example
```

## 중요 제한사항

단일 진동 명령은 duration 값과 관계없이 펌웨어에서 약 800ms 진동으로 처리됩니다. TFLite 주문 인식에는 별도 서버와 호환 `model.tflite`가 필요하며, 해당 모델은 **공개 제공되지 않습니다**. 이번 공통 규칙 적용 중 실물 기기·프록시 조합을 새로 검증하지 않았습니다. [문제 해결(영어)](docs/troubleshooting.md)을 참고하세요.

Usage 배지는 데이터 제공에 동의한 HA Analytics 참여 설치 집계입니다. 미집계·조회 실패는 설치 수 0을 의미하지 않습니다.

## 문서

- [설정 및 옵션(영어)](docs/setup.md)
- [전체 사용 안내·제스처·Spell Canvas·액션·자동화 예제(영어)](docs/user-guide.md)
- [연결 문제 해결 및 진단(영어)](docs/troubleshooting.md)
- [개발·실제 HA 테스트·의존성 안내(영어)](CONTRIBUTING.md)
- [공통 규칙 적용 및 검증 기록(한국어)](STANDARDS.md)

## 지원 및 라이선스

버그는 [Issues](https://github.com/eigger/hass-magic-caster-wand/issues), 질문·기능 제안은 [Discussions](https://github.com/eigger/hass-magic-caster-wand/discussions)에 남겨 주세요. [MIT 라이선스](LICENSE)를 따릅니다.
