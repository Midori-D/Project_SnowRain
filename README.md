# SnowRain Native 개발판

GitHub Actions에서 최신 iOS에 설치할 arm64 IPA를 만드는 개인용 프로젝트입니다.
현재 구현은 원본 오프닝의 텍스트 표시와 읽던 위치 저장입니다.
선택지, 호감도, 이벤트, 배경 및 음악 연출, 원본 저장 데이터 호환은 구현되지 않았습니다.
원작 전체를 플레이할 수 있는 완성판이 아닙니다.

## GitHub 빌드

1. Project_SnowRain 저장소의 Private 표시를 확인합니다.
2. 이 폴더의 내용을 저장소 루트에 올립니다. 숨김 폴더인 .github도 포함합니다.
3. Actions의 Build private iOS IPA에서 Run workflow를 누릅니다.
4. 성공한 실행의 Artifacts에서 SnowRainNative-unsigned를 다운로드하고 ZIP을 풉니다.
5. 안의 SnowRainNative-unsigned.ipa를 SideStore로 가져와 서명 및 설치합니다.

컴파일은 GitHub의 macOS 러너에서 수행합니다. Apple 로그인 정보는 빌드에 필요하지 않습니다.
빌드에 쓰는 Xcode의 iOS SDK 버전과 앱의 실행 대상 iOS 버전은 다를 수 있습니다.
현재 설정은 최소 iOS 16이며 iOS 27 실기기에서 검증이 필요합니다.
macOS 러너 사용량은 GitHub 계정의 Actions 할당량에 포함됩니다.

## 데이터와 검증 상태

Resources/opening.json은 사용자가 제공한 IPA에서 첫 시나리오의 대사 명령을 읽어 만든 개인용 데이터입니다.
첫 시나리오에서 0x0C로 시작해 NUL로 끝나는 CP949 문자열을 추출했습니다.
이 추출만으로 시나리오 명령이나 분기 의미를 복원한 것은 아닙니다.
개발판에는 원본 대사가 포함되므로 사용자가 지정한 비공개 저장소에서 관리합니다.

Windows에서 파일 구성, JSON 및 IPA 패키징 경로를 점검했습니다.
Xcode 컴파일, GitHub Actions 실행, SideStore 설치와 iPhone 구동은 아직 검증되지 않았습니다.
