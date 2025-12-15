import axios, { AxiosError } from 'axios';
import { HybridSearchRequest, HybridSearchResponse } from '../types';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60초 타임아웃
});

// 에러 메시지 변환
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;

    if (axiosError.code === 'ECONNABORTED') {
      return '요청 시간이 초과되었습니다. 다시 시도해주세요.';
    }

    if (!axiosError.response) {
      return '서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.';
    }

    const status = axiosError.response.status;
    const detail = axiosError.response.data?.detail;

    switch (status) {
      case 400:
        return detail || '잘못된 요청입니다.';
      case 404:
        return '요청한 리소스를 찾을 수 없습니다.';
      case 500:
        return detail || '서버 내부 오류가 발생했습니다.';
      case 503:
        return '서비스가 준비되지 않았습니다. 잠시 후 다시 시도해주세요.';
      default:
        return detail || `오류가 발생했습니다. (${status})`;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return '알 수 없는 오류가 발생했습니다.';
};

export const hybridSearch = async (
  request: HybridSearchRequest
): Promise<HybridSearchResponse> => {
  const response = await api.post<HybridSearchResponse>(
    '/api/hybrid-search',
    request
  );
  return response.data;
};

export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// 회사 정보 (DB명 + 표시명)
export interface Company {
  name: string;        // DB 회사명 (삼성, 현대, DB 등)
  displayName: string; // 표시명 (삼성화재, 현대해상 등)
}

export interface CompanyListResponse {
  companies: Company[];
}

export interface Coverage {
  coverage_name: string;
  benefit_amount: number | null;
  product_name: string;
}

export interface CoverageListResponse {
  coverages: Coverage[];
}

export const getCompanies = async (): Promise<CompanyListResponse> => {
  const response = await api.get<CompanyListResponse>('/api/companies');
  return response.data;
};

export const getCompanyCoverages = async (
  companyName: string
): Promise<CoverageListResponse> => {
  const encodedCompanyName = encodeURIComponent(companyName);
  const response = await api.get<CoverageListResponse>(
    `/api/companies/${encodedCompanyName}/coverages`
  );
  return response.data;
};

export interface ProductListResponse {
  products: string[];
}

export const getCompanyProducts = async (
  companyName: string
): Promise<ProductListResponse> => {
  const encodedCompanyName = encodeURIComponent(companyName);
  const response = await api.get<ProductListResponse>(
    `/api/companies/${encodedCompanyName}/products`
  );
  return response.data;
};

export const getProductCoverages = async (
  companyName: string,
  productName: string
): Promise<CoverageListResponse> => {
  const encodedCompanyName = encodeURIComponent(companyName);
  const encodedProductName = encodeURIComponent(productName);
  const response = await api.get<CoverageListResponse>(
    `/api/companies/${encodedCompanyName}/products/${encodedProductName}/coverages`
  );
  return response.data;
};

// 전체 담보 목록 조회 (비교용)
export interface AllCoveragesResponse {
  coverages: string[];
}

export const getAllCoverages = async (): Promise<AllCoveragesResponse> => {
  const response = await api.get<AllCoveragesResponse>('/api/coverages');
  return response.data;
};

export default api;
