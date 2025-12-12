지금 가진 4종 세트(약관 / 사업방법서 / 상품요약서 / 가입설계서)는 **역할이 완전히 다르면서도 서로 강하게 연결된 데이터 패키지**라서, 이걸 잘 분해해서 “온톨로지 + 구조화 DB + 벡터 RAG”로 통합하는 게 핵심입니다.

## **1. 문서별 역할 정리 → 온톨로지 설계의 기준점**

  

### **1) 약관 (삼성_약관.pdf)**

- **내용**: 보통약관 + 엄청나게 많은 특별약관군(암, 2대질병, 특정질병, 입원/수술, 간병, 항암, 검사/치료, 상해진단/수술, 비용/배상, 등)과 각종 별표(질병/수술/행위 분류표, 산정특례 기준 등).
    
- **역할**
    
    - _정의_: 질병군, 상해, 장해, 진단/입원/수술/치료/간병/배상책임 등 “보장 이벤트”의 정의
        
    - _보장 구조_: “암 진단비(유사암 제외)”, “뇌졸중 진단비”, “[갱신형] 암 진단비” 같은 **특별약관(담보)의 리스트 & 세부조항**
        
    - _조건_: 지급사유, 지급하지 않는 사유, 면책, 책임개시일, 소멸시효, 알릴의무 등
        
    

  

👉 온톨로지에서 **Risk / Coverage / Condition / Clause / DiseaseCodeSet** 같은 핵심 클래스를 정의하는 “법전”.

---

### **2) 사업방법서 (삼성_사업설명서.pdf)**

- **내용**:
    
    - 상품명, 유형(1형/2형), 종(1종/3종/4종),
        
    - 각 담보별 보험기간/납입기간/가입나이/납입주기 등이 표로 정리.
        
    
- **역할**
    
    - 상품의 **파라미터 스펙**: 어떤 담보가 어떤 기간/연령에 가입 가능한지, 만기 구조(60세/80세/100세 만기 등), 갱신형 여부 등.
        
    - “3종(납입면제, 해약환급금 미지급형Ⅱ)” 같은 타입별 성격.
        
    

  

👉 온톨로지에서 **ProductVariant / CoverageOption / Eligibility / PremiumParameter** 클래스를 채우는 데이터 소스.

---

### **3) 상품요약서 / 쉬운요약서**

- **내용**:
    
    - 상품 특징, 주요 보장, 유의사항, 민원사례, 시각화된 요약 설명 등.
        
    
- **역할**
    
    - 소비자 친화적 **설명 텍스트** (LLM 답변의 자연어 근거).
        
    - “핵심 체크포인트”와 민원 포인트를 보여주기 때문에, **설명 의무/리스크 포인트 태그**의 좋은 소스.
        
    

  

👉 온톨로지에는 “설명 리소스(ExplanationResource)”나 “ComplaintPattern”류의 보조 엔티티로 연결, RAG에서는 **답변 톤/예시**를 풍부하게 만드는 소스.

---

### **4) 가입설계서 (삼성_가입설계서_2511.pdf)**

- **내용(추정)**:
    
    - 고객별 설계 결과: 선택 담보, 가입금액, 보험기간/납입기간, 보험료, 특약 구성, 피보험자 정보, 납입방식 등.
        
    
- **역할**
    
    - **실제 판매 단위(Product Package)** 구조를 보여주는 샘플 데이터.
        
    - “어떤 조건의 고객에게 어떤 담보 조합이 설계되는지”를 학습/룰화할 수 있는 근거.
        
    

  

👉 온톨로지에서는 **Plan(견적/설계 단위)**, RAG/툴체인에서는 “설계 검증/추천”에 활용.

---

## **2. 온톨로지 구조: 어떤 클래스/관계를 만들 것인가**

  

### **2-1. 최상위 엔티티**

1. **Company**
    
    - name, code (Samsung, Lotte, Meritz, …)
        
    
2. **Product**
    
    - name: “무배당 삼성화재 건강보험 마이헬스 파트너 (2508.12)”
        
    - business_type: 장기손해/장기상해
        
    - effective_date, version (적용일: 2025-09-01 등)
        
    
3. **ProductVariant**
    
    - type: 1형(남)/2형(여), 1종/3종/4종, “해약환급금 미지급형Ⅱ” 등
        
    - attributes: refund_type, waiver_type, etc.
        
    
4. **Coverage (담보/특약 단위)**
    
    - name: “암 진단비(유사암 제외) 특별약관”, “[갱신형] 뇌졸중 진단비(1년50%) 특별약관” 등
        
    - category: 암진단, 2대질병, 특정질병, 입원, 수술, 항암, 간병, 배상책임…
        
    - renewal_type: 갱신형 / 비갱신형
        
    - coverage_group: 암진단군, 2대질병진단군, 특정질병진단군 …(Table of contents의 “특별약관군” 그대로 사용)
        
    
5. **Benefit (보장 이벤트 단위)**
    
    - benefit_type: 진단비 / 입원일당 / 수술비 / 치료비 / 위로금 / 배상책임 등
        
    - payment_form: 정액 / 일당 / 실손 / 비용보전
        
    - amount_rule: 기본금액, 1년50%, 연간1회한, 5회한 등
        
    
6. **RiskEvent / InsuredEvent**
    
    - event_type: 사망, 장해, 암진단, 뇌졸중진단, 급성심근경색, 치매진단, 골절, 화상, 배상책임 등
        
    - severity_level: 경증/중등도/중증/말기 등 (PSI 등급, 말기 정의 활용).
        
    
7. **Condition / Exclusion**
    
    - waiting_period, survival_period
        
    - “보험금을 지급하지 않는 사유”, “계약 전·후 알릴 의무 위반” 등과 연결.
        
    
8. **Disease / Procedure / Code**
    
    - 별표에 있는 분류표들을 그대로 **코드셋**으로 가져옴 (악성신생물, 제자리신생물, 10대 주요암, 뇌졸중, 심근경색, 각종 질환/수술 코드 등).
        
    - ICD/수가코드/산정특례코드를 표준축으로 삼고, 각 담보의 “보장범위”를 코드셋으로 연결.
        
    
9. **Document / DocumentSection / Clause**
    
    - doc_type: Terms, BusinessSpec, ProductSummary, Proposal
        
    - section_type: 보통약관, 특별약관, 별표, Guide Book, 요약서 등.
        
    - clause: 제3조, 제7조, 특정특약 조항, 별표 항목 등.
        
    
10. **Plan (가입설계 결과)**
    
    - selected_coverages, sum_insured_per_coverage, premium, period, etc.
        
    

---

### **2-2. 핵심 관계들**

- Company ──1:N── Product
    
- Product ──1:N── ProductVariant
    
- ProductVariant ──N:M── Coverage (상품마다 다른 특약 조합)
    
- Coverage ──1:N── Benefit
    
- Benefit ──N:M── RiskEvent
    
- Benefit ──N:M── Disease/ProcedureCodeSet
    
- Coverage ──N:M── Condition/Exclusion
    
- Coverage/Benefit ──N:1── DocumentSection(약관/사업방법서/요약서 조항)
    
- Plan ──N:M── Coverage (설계서에서 실제 선택된 담보 조합)
