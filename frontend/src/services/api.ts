import axios from 'axios';
import { HybridSearchRequest, HybridSearchResponse } from '../types';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export interface CompanyListResponse {
  companies: string[];
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

export default api;
