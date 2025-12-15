# Frontend 개발 Task 관리

> 최종 업데이트: 2025-12-15

## 현재 진행 상황

| # | Task | 상태 | 우선순위 | 담당 |
|---|------|------|---------|------|
| 1 | FRONTEND_GUIDE.md 업데이트 | ✅ 완료 | - | - |
| 2 | API 회사명 매핑 수정 | ✅ 완료 | 높음 | - |
| 3 | Frontend API 서비스 회사명 동기화 | ✅ 완료 | 높음 | - |
| 4 | 비교 응답 담보명 표시 버그 수정 | ✅ 완료 | 높음 | - |
| 5 | 자유 질문 모드 추가 | ✅ 완료 | 중간 | - |
| 6 | InfoQueryBuilder 전체 보험사 옵션 | ⏳ 대기 | 중간 | - |
| 7 | 상품 비교 템플릿 확장 (DB 기반) | ⏳ 대기 | 중간 | - |
| 8 | 에러 처리 및 로딩 상태 개선 | ⏳ 대기 | 낮음 | - |

---

## Task 상세

### Task 1: FRONTEND_GUIDE.md 업데이트 ✅

**상태**: 완료 (2025-12-15)

**작업 내용**:
- 시스템 아키텍처 섹션 추가
- UI 구성 상세화 (실제 구현 기반)
- API 연동 섹션 추가
- 컴포넌트 상세 섹션 추가
- 알려진 이슈 및 개발 로드맵 추가

---

### Task 2: API 회사명 매핑 수정 ✅

**상태**: 완료 (2025-12-15)

**문제점**:
- DB 회사명: `삼성`, `현대`, `DB`, `KB`, `한화`, `롯데`, `메리츠`, `흥국`
- Frontend 사용: `삼성화재`, `현대해상`, `DB손보` 등 풀네임

**완료된 작업**:
- [x] `COMPANY_DISPLAY_NAMES` 매핑 추가 (DB명 → 표시명)
- [x] `COMPANY_ALIASES` 매핑 추가 (별칭 → DB명)
- [x] `resolve_company_name()` 헬퍼 함수 추가
- [x] `get_display_name()` 헬퍼 함수 추가
- [x] `/api/companies` 응답에 `name`, `displayName` 포함
- [x] `/api/companies/{company}/products` 별칭 해석 지원
- [x] `/api/companies/{company}/products/{product}/coverages` 별칭 해석 지원
- [x] `/api/companies/{company}/coverages` 별칭 해석 지원

**변경된 API 응답**:
```json
// GET /api/companies
{
  "companies": [
    {"name": "삼성", "displayName": "삼성화재"},
    {"name": "현대", "displayName": "현대해상"},
    ...
  ]
}
```

**관련 파일**:
- `api/server.py` - API 엔드포인트 (수정됨)

---

### Task 3: Frontend API 서비스 회사명 동기화 ✅

**상태**: 완료 (2025-12-15)

**완료된 작업**:
- [x] `api.ts`에 `Company` 인터페이스 추가 (`name`, `displayName`)
- [x] `CompanyListResponse` 타입 업데이트 (`Company[]`)
- [x] `InfoQueryBuilder.tsx` 수정:
  - `companies` 상태 타입: `string[]` → `Company[]`
  - `selectedCompany` 상태 타입: `string` → `Company | null`
  - API 호출 시 `company.name` (DB명) 사용
  - UI 표시 시 `company.displayName` (표시명) 사용
  - 쿼리 생성 시 `displayName` 사용

**변경된 파일**:
- `frontend/src/services/api.ts` - Company 인터페이스 추가
- `frontend/src/components/InfoQueryBuilder.tsx` - 회사 타입 및 로직 수정

---

### Task 4: 비교 응답 담보명 표시 버그 수정 ✅

**상태**: 완료 (2025-12-15)

**문제점**:
- 템플릿 선택 후 다른 담보를 질문해도 템플릿의 기본 담보명이 응답에 표시됨
- 예: "다빈치로봇 암수술비 비교" 템플릿 선택 후 "경계성종양 및 제자리암 비교" 질문 시 "다빈치 비교"로 표시

**원인**:
- 템플릿 기반 검색 시 NL entities의 coverages를 템플릿의 `coverageKeyword`로 덮어씀
- 사용자 쿼리에서 추출한 담보명이 무시됨

**완료된 작업**:
- [x] 쿼리에서 엔티티 추출을 항상 먼저 수행하도록 변경
- [x] 템플릿 coverageKeyword는 쿼리에서 담보 추출 실패 시에만 폴백으로 사용
- [x] 폴백 담보 추출 시 모든 매칭 키워드를 수집 (단일 키워드가 아닌 다중 키워드)
- [x] 담보 키워드 목록 확장 (뇌졸중, 급성심근경색, 다빈치 추가)
- [x] NL mapper의 `keywords` 필드에서도 담보 키워드 추출 (coverages가 빈 경우)

**변경된 파일**:
- `api/server.py` - NL entity 추출 로직 및 폴백 담보 추출 로직 수정

---

### Task 5: 자유 질문 모드 추가 ✅

**상태**: 완료 (2025-12-15)

**현재 문제**:
- 카테고리 선택 없이는 입력창 비활성화
- 사용자가 자유롭게 질문할 수 없음

**완료된 작업**:
- [x] `queryTemplates.ts`에 "자유 질문" 카테고리 및 템플릿 추가
- [x] `categoryMetadata`에 "자유 질문" 메타데이터 추가
- [x] `ChatInterface.tsx` 입력창 활성화 조건 수정
- [x] "자유 질문" 선택 시 환영 메시지 UI 추가
- [x] 자유 질문 시 Vector 검색 활용 가능

**추가된 템플릿**:
- 🔍 자유롭게 질문하기
- 면책/제외 조항 질문
- 보장 조건 질문
- 갱신/해지 관련 질문

**변경된 파일**:
- `frontend/src/data/queryTemplates.ts` - 자유 질문 템플릿 및 메타데이터 추가
- `frontend/src/components/ChatInterface.tsx` - 입력창 활성화 및 환영 UI 추가

---

### Task 6: InfoQueryBuilder 전체 보험사 옵션 추가

**상태**: ⏳ 대기

**작업 내용**:
- [ ] Step 1에 "전체 보험사 비교" 옵션 추가
- [ ] 전체 선택 시 모든 보험사에 대해 비교 쿼리 생성
- [ ] 다중 선택 UI 구현 (체크박스)

**관련 파일**:
- `frontend/src/components/InfoQueryBuilder.tsx`

---

### Task 7: 상품 비교 템플릿 확장

**상태**: ⏳ 대기

**현재 상황**:
- DB에 294개 담보 존재
- Frontend에 5개 비교 템플릿만 등록

**작업 내용**:
- [ ] API에서 담보 목록 조회하여 동적 템플릿 생성
- [ ] 또는 주요 담보 기반 추가 템플릿 등록
- [ ] 검색/필터 기능 추가

**후보 담보**:
- 암진단비 (일반암)
- 뇌졸중 진단비
- 급성심근경색 진단비
- 입원일당
- 수술비 (일반)

**관련 파일**:
- `frontend/src/data/queryTemplates.ts`
- `frontend/src/components/Sidebar.tsx`

---

### Task 8: 에러 처리 및 로딩 상태 개선

**상태**: ⏳ 대기

**작업 내용**:
- [ ] API 에러 시 사용자 친화적 메시지 표시
- [ ] 네트워크 오류 재시도 기능
- [ ] 로딩 스켈레톤 UI 적용
- [ ] 타임아웃 처리

**관련 파일**:
- `frontend/src/services/api.ts`
- `frontend/src/components/ChatInterface.tsx`
- `frontend/src/components/InfoQueryBuilder.tsx`

---

## 완료된 Task 히스토리

| 날짜 | Task | 설명 |
|------|------|------|
| 2025-12-15 | FRONTEND_GUIDE.md 업데이트 | 시스템 현황 기반 문서 전면 개정 |
| 2025-12-15 | API 회사명 매핑 수정 | 별칭→DB명 변환, 표시명 추가 |
| 2025-12-15 | Frontend API 서비스 동기화 | Company 인터페이스, InfoQueryBuilder 수정 |
| 2025-12-15 | 비교 응답 담보명 표시 버그 수정 | 쿼리 담보 우선, 템플릿 키워드 폴백 |
| 2025-12-15 | 중복 담보 섹션 버그 수정 | normalize_coverage_name() 함수 추가로 중복 제거 |
| 2025-12-15 | 유사암 제목 매칭 버그 수정 | get_display_title() 개선, 쿼리 키워드 추출 |
| 2025-12-15 | 경계성종양 N/A 메시지 개선 | "해당 담보 정보를 찾을 수 없습니다" 메시지로 변경 |
| 2025-12-15 | 자유 질문 모드 추가 | "자유 질문" 카테고리, 입력창 활성화, Vector 검색 활용 |
| 2025-12-15 | LLM 응답 생성 활성화 | 자유 질문 시 Vector 검색 + LLM 답변 생성 연동 |

---

## 참고 사항

### DB 회사명 매핑 (NL Mapper)

```python
COMPANY_ALIASES = {
    "삼성": ["삼성화재", "삼성생명", "삼성손보"],
    "DB": ["동부", "동부화재", "DB손보", "DB손해보험"],
    "현대": ["현대해상", "현대생명", "현대손보"],
    "한화": ["한화손보", "한화손해보험", "한화생명"],
    "롯데": ["롯데손보", "롯데손해보험"],
    "KB": ["KB손보", "KB손해보험", "KB생명"],
    "메리츠": ["메리츠화재", "메리츠손보"],
    "흥국": ["흥국화재", "흥국생명"],
}
```

### 현재 등록된 상품

| 회사 | 상품명 |
|------|--------|
| 삼성 | 무배당 삼성화재 건강보험 마이헬스 파트너 |
| 현대 | 무배당 현대해상 건강보험 |
| DB | 무배당 DB손해보험 실속건강보험 |
| KB | 무배당 KB손해보험 실속건강보험 |
| 한화 | 무배당 한화손해보험 건강보험 |
| 롯데 | 무배당 롯데손해보험 건강보험 |
| 메리츠 | 무배당 메리츠화재 건강보험 |
| 흥국 | 무배당 흥국화재 건강보험 |
