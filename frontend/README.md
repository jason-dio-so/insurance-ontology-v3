# 보험 온톨로지 AI 챗봇 - Frontend

ChatGPT 스타일의 보험 상품 비교 및 조회 시스템 프론트엔드입니다.

## 🚀 시작하기

### 1. 의존성 설치

```bash
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 http://localhost:5173 으로 접속하세요.

### 3. 백엔드 서버 실행 (별도 터미널)

```bash
cd ..
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

## 📁 프로젝트 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx          # 왼쪽 쿼리 템플릿
│   │   ├── ChatInterface.tsx    # 채팅 인터페이스
│   │   ├── Message.tsx           # 메시지 컴포넌트
│   │   └── ComparisonTable.tsx   # 비교 테이블
│   ├── services/
│   │   └── api.ts                # API 호출
│   ├── types/
│   │   └── index.ts              # TypeScript 타입
│   ├── data/
│   │   └── queryTemplates.ts     # 쿼리 템플릿 데이터
│   ├── App.tsx                   # 메인 앱
│   ├── main.tsx                  # 엔트리 포인트
│   └── index.css                 # 전역 스타일
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## 🎨 주요 기능

### 왼쪽 사이드바
- **쿼리 템플릿**: 미리 정의된 질문 템플릿
- **카테고리 필터**: 상품 비교, 담보 조회, 가입 조건 등
- **검색 기능**: 템플릿 검색

### 오른쪽 채팅 인터페이스
- **ChatGPT 스타일 UI**: 친숙한 대화형 인터페이스
- **실시간 응답**: LLM 기반 자연어 응답
- **비교 테이블**: 여러 상품 비교 시 표 형태로 표시
- **참고 자료**: 응답 근거가 된 원본 문서 표시

## 🛠️ 기술 스택

- **React 18** - UI 라이브러리
- **TypeScript** - 타입 안전성
- **Vite** - 빠른 개발 서버
- **Tailwind CSS** - 유틸리티 CSS 프레임워크
- **Axios** - HTTP 클라이언트
- **React Markdown** - 마크다운 렌더링

## 📝 사용 예시

### 상품 비교
```
삼성화재와 현대해상의 암진단비를 비교해주세요
```

### 담보 조회
```
KB손보 암 진단금은 얼마인가요?
```

### 가입 조건
```
40세 남성이 가입할 수 있는 암보험은?
```

## 🔧 빌드

프로덕션 빌드:

```bash
npm run build
```

빌드된 파일은 `dist/` 디렉토리에 생성됩니다.

## 📦 배포

빌드 후 `dist/` 디렉토리를 정적 파일 호스팅 서비스에 배포하세요.
- Vercel
- Netlify
- GitHub Pages
- AWS S3 + CloudFront

## 🎯 향후 계획

- [ ] 사용자 프로필 관리
- [ ] 대화 히스토리 저장
- [ ] 음성 입력 지원
- [ ] PDF 다운로드 기능
- [ ] 다크/라이트 모드 토글
