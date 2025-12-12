# Frontend-Backend API 명세서

## 개요

이 문서는 프론트엔드에서 백엔드로 요청하는 API 엔드포인트와 처리 방식을 정리합니다.

---

## API 엔드포인트 목록

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 서버 상태 확인 |
| `/api/companies` | GET | 보험사 목록 조회 |
| `/api/companies/{company}/products` | GET | 특정 보험사의 상품 목록 |
| `/api/companies/{company}/coverages` | GET | 특정 보험사의 담보 목록 |
| `/api/companies/{company}/products/{product}/coverages` | GET | 특정 상품의 담보 목록 |
| `/api/hybrid-search` | POST | 하이브리드 검색 (메인 API) |
| `/api/compare` | POST | 상품 비교 (미구현) |

---

## 1. `/api/hybrid-search` (메인 검색 API)

### 요청 (Request)

```typescript
interface HybridSearchRequest {
  query: string;                    // 사용자 질문
  userProfile?: UserProfile;        // 사용자 프로필 (선택)
  selectedCategories?: string[];    // 선택된 카테고리
  selectedCoverageTags?: string[];  // 선택된 담보 태그
  lastCoverage?: string;            // 이전 대화의 담보명 (컨텍스트)
  templateId?: string;              // 템플릿 ID
  searchParams?: SearchParams;      // 구조화된 검색 파라미터
}

interface SearchParams {
  coverageKeyword?: string;   // 담보 키워드
  exactMatch?: boolean;       // 정확 매칭 여부
  excludeKeywords?: string[]; // 제외 키워드
  docTypes?: string[];        // 문서 타입 제한
}
```

### 응답 (Response)

```typescript
interface HybridSearchResponse {
  answer: string;                      // LLM 생성 답변
  comparisonTable?: ComparisonResult[]; // 비교 테이블 데이터
  sources?: Source[];                  // 출처 정보
  coverage?: string;                   // 사용된 담보명 (컨텍스트용)
}

interface ComparisonResult {
  company: string;
  product: string;
  coverage: string;
  benefit: string;
  premium?: string;
  notes?: string;
}
```

### 처리 로직 분기

```
┌─────────────────────────────────────────────────────────────────┐
│                    /api/hybrid-search                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ NL Mapper로     │
                    │ 엔티티 추출     │
                    │ (회사명, 담보)  │
                    └─────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌────────────┐   ┌────────────┐   ┌────────────┐
     │ 회사 1개 + │   │ 회사 2개+  │   │ 일반 검색  │
     │ Info 템플릿│   │ 비교 요청  │   │            │
     └────────────┘   └────────────┘   └────────────┘
              │               │               │
              ▼               ▼               ▼
     ┌────────────┐   ┌────────────┐   ┌────────────┐
     │ InfoExtractor│ │ ProductComparer│ │ HybridRetriever│
     │ 정보 추출  │   │ 상품 비교  │   │ 벡터 검색  │
     └────────────┘   └────────────┘   └────────────┘
```

---

## 2. 정보 조회 (InfoExtractor)

### 지원 템플릿 ID

| templateId | 설명 | 검색 키워드 |
|------------|------|------------|
| `coverage-start-date` | 보장개시일 | 보장개시, 면책기간, 책임개시 |
| `coverage-limit` | 보장한도 | 보장한도, 지급한도, 지급제한 |
| `enrollment-age` | 가입나이 | 가입, 나이 |
| `exclusions` | 면책사항 | 면책, 보장제외, 보상하지 |
| `renewal-info` | 갱신기간/비율 | 갱신, 감액 |

### 처리 흐름

```
요청 → 회사/담보 매칭 → 관련 약관 조항 검색 → 패턴 파싱 → LLM 응답 생성
```

---

## 3. 상품 비교 (ProductComparer)

### 호출 조건

- 쿼리에 2개 이상의 보험사 이름 포함
- 담보 키워드 존재

### 처리 흐름

```
1. Multi-company 검색 실행
2. 각 회사별 비교 데이터 추출
   - DB에서 담보/보장금액 직접 조회
   - 약관에서 가입나이 조건 추출
3. 비교 테이블 생성
4. 추천 메시지 생성 (보장금액 최고, 보험료 최저 등)
```

### 응답 예시

```json
{
  "answer": "# 다빈치로봇 암수술비 비교\n\n**삼성화재** (마이헬스파트너)\n- 보장금액: 3,000만원\n...",
  "comparisonTable": [
    {"company": "삼성화재", "product": "마이헬스파트너", "coverage": "다빈치로봇 암수술비", "benefit": "3,000만원"},
    {"company": "현대해상", "product": "하이라이프", "coverage": "다빈치로봇 암수술비", "benefit": "2,500만원"}
  ],
  "sources": [...]
}
```

---

## 4. 보험사/상품/담보 목록 API

### GET `/api/companies`

```json
{
  "companies": ["삼성화재", "현대해상", "DB손보", "KB손보", "한화손보", "롯데손보", "흥국화재"]
}
```

### GET `/api/companies/{company}/products`

```json
{
  "products": ["마이헬스파트너 암보험", "무배당 건강보험 플러스"]
}
```

### GET `/api/companies/{company}/products/{product}/coverages`

```json
{
  "coverages": [
    {"coverage_name": "암진단비", "benefit_amount": 30000000, "product_name": "마이헬스파트너"},
    {"coverage_name": "뇌출혈진단비", "benefit_amount": 20000000, "product_name": "마이헬스파트너"}
  ]
}
```

---

## 5. 상태 관리 규칙

### 5.0 초기화 규칙

**메인화면으로 돌아오면 모든 상태 초기화**

| 트리거 | 초기화 대상 |
|--------|------------|
| "처음으로" 버튼 클릭 | 모든 상태 초기화 |
| 다른 카테고리 선택 | 이전 카테고리 관련 상태 초기화 |

**초기화되는 상태:**
- `selectedCategory` → null
- `selectedTemplate` → null
- `messages` → []
- `input` → ""
- `currentTemplate` → null
- `lastCoverage` → null
- `showInfoQueryBuilder` → false
- `showReturnButton` → false

### 상태 흐름 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                        메인화면                              │
│              (카테고리 미선택, 모든 상태 초기화)              │
└─────────────────────────────────────────────────────────────┘
                              │
                    카테고리 선택
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     카테고리 선택됨                          │
│              (템플릿 목록 표시)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                    템플릿/담보 선택
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     작업 진행 중                             │
│              (메시지 입력/조회)                              │
└─────────────────────────────────────────────────────────────┘
                              │
               "처음으로" 또는 다른 카테고리
                              ▼
                    ┌──────────────┐
                    │  상태 초기화  │
                    └──────────────┘
                              │
                              ▼
                        메인화면
```

---

## 6. Frontend 사용 패턴

### 6.1 상품 비교 카테고리

```
사용자 흐름:
1. 메인화면 표시 (환영 메시지 + 카테고리 안내)
2. 사이드바에서 "상품 비교" 카테고리 선택
   - 담보 템플릿 목록 표시
   - 입력창: 비활성화 ("왼쪽에서 비교할 담보를 선택해주세요")
3. 담보 템플릿 선택 (예: "암진단비 비교")
   - 메인 영역: 선택한 담보 안내 메시지 표시
   - 입력창: 활성화 + 템플릿 example 자동 입력
4. 메시지 수정/전송
5. 결과 표시 (답변 + 비교 테이블 + 출처)

상태 변화:
- selectedCategory: null → "상품 비교"
- currentTemplate: null → 선택한 템플릿
- input: "" → template.example
- messages: [] → [user, assistant]

API 호출:
POST /api/hybrid-search
{
  "query": "삼성화재와 현대해상의 암진단비를 비교해주세요",
  "templateId": "compare-cancer-diagnosis",
  "searchParams": {
    "coverageKeyword": "암진단",
    "exactMatch": false,
    "docTypes": ["proposal"]
  }
}
```

### 6.2 상품/담보 설명 카테고리

```
사용자 흐름:
1. 사이드바에서 "상품/담보 설명" 카테고리 선택
2. 정보 유형 선택 (예: "보장개시일")
3. InfoQueryBuilder 모달 표시:
   - Step 1: 보험사 선택 (API: /api/companies)
   - Step 2: 상품 선택 (API: /api/companies/{company}/products)
   - Step 3: 담보 선택 (API: /api/companies/{company}/products/{product}/coverages)
   - Step 4: 정보 유형 선택 (이미 선택됨)
4. "조회하기" 클릭

API 호출:
POST /api/hybrid-search
{
  "query": "삼성화재 암진단비의 보장개시일은 언제인가요?",
  "templateId": "coverage-start-date"
}
```

---

## 7. 데이터 흐름 다이어그램

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                     │
│  ┌─────────────┐    ┌──────────────────┐    ┌──────────────────────────┐ │
│  │   Sidebar   │───▶│  ChatInterface   │───▶│    InfoQueryBuilder      │ │
│  │ (카테고리)  │    │ (메시지 전송)    │    │ (정보 조회용 모달)       │ │
│  └─────────────┘    └──────────────────┘    └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Axios
┌──────────────────────────────────────────────────────────────────────────┐
│                          Backend (FastAPI)                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                       /api/hybrid-search                            │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────────┐   │  │
│  │  │  NL Mapper  │──▶│ 엔티티 분석 │──▶│ InfoExtractor /         │   │  │
│  │  │  (자연어)   │   │ (회사/담보) │   │ ProductComparer         │   │  │
│  │  └─────────────┘   └─────────────┘   └─────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                         PostgreSQL                                  │  │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌───────────────────────┐ │  │
│  │  │ company │  │ product │  │ coverage │  │ document_clause       │ │  │
│  │  └─────────┘  └─────────┘  └──────────┘  │ (약관 텍스트)         │ │  │
│  │                                          └───────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 8. NL Mapper 회사명 별칭 매핑

사용자가 입력한 회사명 별칭을 DB의 실제 회사명으로 변환합니다.

### 지원 별칭

| DB 회사명 | 지원 별칭 |
|-----------|-----------|
| 삼성 | 삼성화재, 삼성생명, 삼성손보, 삼성손해보험 |
| DB | 동부, 동부화재, 동부손보, 동부손해보험, DB손보, DB손해보험, DB화재 |
| 현대 | 현대해상, 현대생명, 현대손보, 현대손해보험 |
| 한화 | 한화손보, 한화손해보험, 한화생명, 한화화재 |
| 롯데 | 롯데손보, 롯데손해보험, 롯데화재 |
| KB | KB손보, KB손해보험, KB생명 |
| 메리츠 | 메리츠화재, 메리츠손보, 메리츠손해보험 |
| 흥국 | 흥국화재, 흥국생명, 흥국손보 |

### 예시

```
입력: "삼성과 동부 비교해줘"
추출: companies = ['삼성', 'DB']

입력: "삼성화재와 현대해상 암진단비"
추출: companies = ['삼성', '현대']
```

### 관련 파일

- `ontology/nl_mapping.py`: `NLMapper.COMPANY_ALIASES` 딕셔너리

---

## 9. 향후 개선 필요 사항

1. ~~**상품 비교 UI 개선**: 카테고리 선택 → 담보 선택 → 입력 활성화 흐름~~ ✅ 완료
2. **LLM 응답 활성화**: 현재 일반 검색은 LLM 비활성화 상태
3. `/api/compare` 엔드포인트 구현 완료 필요
