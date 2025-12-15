export interface QueryTemplate {
  id: string;
  category: string;
  title: string;
  description: string;
  example: string;
  tags: string[];
  // 구조화된 검색 파라미터
  searchParams?: {
    coverageKeyword?: string;  // 정확한 담보 키워드
    exactMatch?: boolean;      // 정확히 매칭할 것인지
    excludeKeywords?: string[]; // 제외할 키워드
    docTypes?: string[];       // 문서 타입 제한
  };
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  comparisonTable?: ComparisonResult[];
  sources?: Source[];
  isError?: boolean;
}

export interface ComparisonResult {
  company: string;
  product: string;
  coverage: string;
  benefit: string;
  premium?: string;
  notes?: string;
}

export interface Source {
  company: string;
  product: string;
  clause: string;
  docType?: string;
}

export interface HybridSearchRequest {
  query: string;
  userProfile?: UserProfile;
  selectedCategories?: string[];
  selectedCoverageTags?: string[];
  lastCoverage?: string;
  // 템플릿 기반 검색 파라미터
  templateId?: string;
  searchParams?: {
    coverageKeyword?: string;
    exactMatch?: boolean;
    excludeKeywords?: string[];
    docTypes?: string[];
  };
}

export interface HybridSearchResponse {
  answer: string;
  comparisonTable?: ComparisonResult[];
  sources?: Source[];
  coverage?: string;
}

export interface UserProfile {
  birthDate: string;
  gender: 'male' | 'female';
  name?: string;
  phone?: string;
  email?: string;
}
