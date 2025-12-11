import { QueryTemplate } from '../types';

export const queryTemplates: QueryTemplate[] = [
  // 상품 비교 - 실제 데이터 기반
  {
    id: 'compare-robot-surgery',
    category: '상품 비교',
    title: '다빈치로봇 암수술비 비교',
    description: '7개 보험사의 다빈치로봇 암수술비를 비교합니다',
    example: '삼성화재와 현대해상의 다빈치로봇 암수술비를 비교해주세요',
    tags: ['비교', '로봇수술', '암수술'],
    searchParams: {
      coverageKeyword: '다빈치',
      exactMatch: false,
      excludeKeywords: [],
      docTypes: ['proposal'],
    },
  },
  {
    id: 'compare-brain-hemorrhage',
    category: '상품 비교',
    title: '뇌출혈 진단비 비교',
    description: '7개 보험사의 뇌출혈 진단비를 비교합니다',
    example: '삼성화재와 현대해상의 뇌출혈 진단비를 비교해주세요',
    tags: ['비교', '뇌출혈', '진단비'],
    searchParams: {
      coverageKeyword: '뇌출혈',
      exactMatch: false,
      excludeKeywords: [],
      docTypes: ['proposal'],
    },
  },
  {
    id: 'compare-quasi-cancer-surgery',
    category: '상품 비교',
    title: '유사암 수술비 비교',
    description: '4개 보험사의 유사암 수술비를 비교합니다',
    example: '롯데손보와 한화손보의 유사암 수술비를 비교해주세요',
    tags: ['비교', '유사암', '수술비'],
    searchParams: {
      coverageKeyword: '유사암수술',
      exactMatch: false,
      excludeKeywords: [],
      docTypes: ['proposal'],
    },
  },
  {
    id: 'compare-carcinoma-in-situ',
    category: '상품 비교',
    title: '제자리암 진단비 비교',
    description: '삼성화재와 한화손보의 제자리암 진단비를 비교합니다 (각 600만원)',
    example: '삼성화재와 한화손보의 제자리암 진단비를 비교해주세요',
    tags: ['비교', '제자리암', '진단비', '유사암'],
    searchParams: {
      coverageKeyword: '제자리암',
      exactMatch: false,
      excludeKeywords: [],
      docTypes: ['proposal'],
    },
  },
  {
    id: 'compare-borderline-tumor',
    category: '상품 비교',
    title: '경계성종양 진단비 비교',
    description: '삼성화재와 한화손보의 경계성종양 진단비를 비교합니다 (각 600만원)',
    example: '삼성화재와 한화손보의 경계성종양 진단비를 비교해주세요',
    tags: ['비교', '경계성종양', '진단비', '유사암'],
    searchParams: {
      coverageKeyword: '경계성종양',
      exactMatch: false,
      excludeKeywords: [],
      docTypes: ['proposal'],
    },
  },
  // 상품/담보 설명
  {
    id: 'coverage-start-date',
    category: '상품/담보 설명',
    title: '보장개시일',
    description: '특정 담보의 보장개시일을 확인합니다',
    example: '삼성화재 암진단비의 보장개시일은 언제인가요?',
    tags: ['보장개시일', '면책기간', '약관'],
  },
  {
    id: 'coverage-limit',
    category: '상품/담보 설명',
    title: '보장한도',
    description: '담보의 보장한도와 지급 제한사항을 확인합니다',
    example: '현대해상 암입원비의 보장한도는 어떻게 되나요?',
    tags: ['보장한도', '지급제한', '약관'],
  },
  {
    id: 'enrollment-age',
    category: '상품/담보 설명',
    title: '가입나이',
    description: '상품 또는 담보의 가입 가능 나이를 확인합니다',
    example: '삼성화재 다빈치로봇 암수술비는 몇 세까지 가입할 수 있나요?',
    tags: ['가입나이', '가입조건', '연령제한'],
  },
  {
    id: 'exclusions',
    category: '상품/담보 설명',
    title: '면책사항',
    description: '보장이 제외되는 경우와 면책기간을 확인합니다',
    example: '한화손보 암진단비의 면책사항은 무엇인가요?',
    tags: ['면책', '보장제외', '약관'],
  },
  {
    id: 'renewal-info',
    category: '상품/담보 설명',
    title: '갱신기간 및 비율',
    description: '갱신형 담보의 갱신주기와 감액비율을 확인합니다',
    example: '롯데손보 다빈치로봇 암수술비는 갱신형인가요? 감액비율은 얼마인가요?',
    tags: ['갱신', '감액', '갱신형'],
  },

  // 간단한 사용법 안내
  {
    id: 'usage-guide',
    category: '사용법',
    title: '💡 시스템 사용 방법',
    description: '상품 비교 기능 사용 방법',
    example: '이 시스템은 2개 이상의 보험사 상품을 비교하거나, 특정 회사의 상품/담보 정보를 조회할 수 있습니다.',
    tags: ['가이드', '사용법'],
  },
];

export const categories = Array.from(
  new Set(queryTemplates.map((t) => t.category))
);

// 카테고리별 메타데이터
export interface CategoryMetadata {
  name: string;
  icon: string;
  colorClass: string;
  description: string;
}

export const categoryMetadata: CategoryMetadata[] = [
  {
    name: '상품 비교',
    icon: '💡',
    colorClass: 'text-blue-400',
    description: '여러 보험사의 담보를 비교하여 최적의 선택을 도와드립니다',
  },
  {
    name: '상품/담보 설명',
    icon: '📊',
    colorClass: 'text-green-400',
    description: '특정 담보의 보장금액, 조건, 면책사항 등을 상세하게 확인할 수 있습니다',
  },
  {
    name: '사용법',
    icon: '❓',
    colorClass: 'text-purple-400',
    description: '보험 온톨로지 AI 시스템 사용 방법을 안내합니다',
  },
];
