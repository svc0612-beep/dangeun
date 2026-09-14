당근 클론 - 프론트엔드

이 폴더의 src\ 안을 C:\danggeun\frontend\src\ 에 그대로 덮어쓰면 됨
(main.jsx 는 기존 것 그대로 두기 — import './index.css' 만 있으면 됨)

폴더 구조
  App.jsx          화면 전환만
  api.js           서버와 이야기하는 곳
  utils.js         가격·시간 표시 등 자잘한 도구
  index.css        스타일 불러오기만
  components\      여러 화면에서 쓰는 조각
  screens\         실제 화면들
  styles\          역할별 스타일

필요한 패키지
  npm install lucide-react
