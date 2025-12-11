import React, { useState, useEffect } from 'react';
import { getCompanies, getCompanyProducts, getProductCoverages, Coverage } from '../services/api';

interface InfoQueryBuilderProps {
  onQuerySubmit: (query: string, templateId: string) => void;
  onClose: () => void;
  preselectedInfoType?: string;
}

type InfoType = {
  id: string;
  label: string;
  description: string;
};

const INFO_TYPES: InfoType[] = [
  {
    id: 'coverage-start-date',
    label: '보장개시일',
    description: '보장이 시작되는 시점과 면책기간',
  },
  {
    id: 'coverage-limit',
    label: '보장한도',
    description: '보장금액의 한도와 지급 제한사항',
  },
  {
    id: 'enrollment-age',
    label: '가입나이',
    description: '가입 가능한 나이 범위',
  },
  {
    id: 'exclusions',
    label: '면책사항',
    description: '보장이 제외되는 경우',
  },
  {
    id: 'renewal-info',
    label: '갱신기간 및 비율',
    description: '갱신 주기와 감액 비율',
  },
];

const InfoQueryBuilder: React.FC<InfoQueryBuilderProps> = ({
  onQuerySubmit,
  onClose,
  preselectedInfoType,
}) => {
  const [step, setStep] = useState(1);
  const [companies, setCompanies] = useState<string[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [products, setProducts] = useState<string[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>('');
  const [coverages, setCoverages] = useState<Coverage[]>([]);
  const [selectedCoverage, setSelectedCoverage] = useState<Coverage | null>(
    null
  );
  const [selectedInfoType, setSelectedInfoType] = useState<InfoType | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // Load companies on mount
  useEffect(() => {
    loadCompanies();
  }, []);

  // Set preselected info type on mount
  useEffect(() => {
    if (preselectedInfoType) {
      const infoType = INFO_TYPES.find((t) => t.id === preselectedInfoType);
      if (infoType) {
        setSelectedInfoType(infoType);
      }
    }
  }, [preselectedInfoType]);

  const loadCompanies = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getCompanies();
      setCompanies(result.companies);
    } catch (err) {
      setError('회사 목록을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async (companyName: string) => {
    setLoading(true);
    setError('');
    try {
      const result = await getCompanyProducts(companyName);
      setProducts(result.products);
    } catch (err) {
      setError('상품 목록을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadProductCoverages = async (companyName: string, productName: string) => {
    setLoading(true);
    setError('');
    try {
      const result = await getProductCoverages(companyName, productName);
      setCoverages(result.coverages);
    } catch (err) {
      setError('담보 목록을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCompanySelect = async (company: string) => {
    setSelectedCompany(company);
    await loadProducts(company);
    setStep(2);
  };

  const handleProductSelect = async (product: string) => {
    setSelectedProduct(product);
    await loadProductCoverages(selectedCompany, product);
    setStep(3);
  };

  const handleCoverageSelect = (coverage: Coverage) => {
    setSelectedCoverage(coverage);
    // If info type is preselected, stay on step 3; otherwise go to step 4
    if (!preselectedInfoType) {
      setStep(4);
    }
  };

  const handleInfoTypeSelect = (infoType: InfoType) => {
    setSelectedInfoType(infoType);
  };

  const handleSubmit = () => {
    if (!selectedCompany || !selectedProduct || !selectedCoverage || !selectedInfoType) {
      setError('모든 항목을 선택해주세요.');
      return;
    }

    // Generate query
    const queryTemplates: Record<string, string> = {
      'coverage-start-date': `${selectedCompany} ${selectedCoverage.coverage_name}의 보장개시일은 언제인가요?`,
      'coverage-limit': `${selectedCompany} ${selectedCoverage.coverage_name}의 보장한도는 어떻게 되나요?`,
      'enrollment-age': `${selectedCompany} ${selectedCoverage.coverage_name}는 몇 세까지 가입할 수 있나요?`,
      exclusions: `${selectedCompany} ${selectedCoverage.coverage_name}의 면책사항은 무엇인가요?`,
      'renewal-info': `${selectedCompany} ${selectedCoverage.coverage_name}는 갱신형인가요? 감액비율은 얼마인가요?`,
    };

    const query = queryTemplates[selectedInfoType.id];
    onQuerySubmit(query, selectedInfoType.id);
    onClose();
  };

  const handleBack = () => {
    if (step === 2) {
      setSelectedCompany('');
      setProducts([]);
      setStep(1);
    } else if (step === 3) {
      setSelectedProduct('');
      setCoverages([]);
      setStep(2);
    } else if (step === 4) {
      setSelectedCoverage(null);
      setStep(3);
    }
  };

  const formatAmount = (amount: number | null) => {
    if (!amount) return 'N/A';
    return `${amount.toLocaleString()}원`;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-blue-600 text-white px-4 py-3 flex justify-between items-center flex-shrink-0">
          <h2 className="text-lg font-bold">상품/담보 정보 조회</h2>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-200 transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Progress Steps - Minimized */}
        <div className="bg-gray-50 px-4 py-2 flex-shrink-0 border-b border-gray-200">
          <div className="flex items-center justify-center gap-2 text-sm">
            {(preselectedInfoType ? [1, 2, 3] : [1, 2, 3, 4]).map((s) => (
              <React.Fragment key={s}>
                <div className="flex items-center gap-1">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                      step >= s
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-300 text-gray-600'
                    }`}
                  >
                    {s}
                  </div>
                  <span className={step >= s ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                    {s === 1 && '회사'}
                    {s === 2 && '상품'}
                    {s === 3 && '담보'}
                    {s === 4 && '정보'}
                  </span>
                </div>
                {s < (preselectedInfoType ? 3 : 4) && (
                  <div
                    className={`w-8 h-0.5 ${
                      step > s ? 'bg-blue-600' : 'bg-gray-300'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto flex-1">
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <>
              {/* Step 1: Company Selection */}
              {step === 1 && (
                <div>
                  <h3 className="text-base font-bold mb-3 text-gray-800">
                    보험사를 선택하세요
                  </h3>
                  <div className="grid grid-cols-4 gap-2">
                    {companies.map((company) => (
                      <button
                        key={company}
                        onClick={() => handleCompanySelect(company)}
                        className="px-2 py-2.5 border-2 border-gray-300 rounded-md hover:border-blue-500 hover:bg-blue-50 transition-colors text-center text-sm font-medium text-gray-800"
                      >
                        {company}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 2: Product Selection */}
              {step === 2 && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    상품을 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    선택한 보험사: <strong>{selectedCompany}</strong>
                  </div>
                  <div className="space-y-2">
                    {products.map((product, index) => (
                      <button
                        key={index}
                        onClick={() => handleProductSelect(product)}
                        className={`w-full px-3 py-2 border-2 rounded-md transition-colors text-left ${
                          selectedProduct === product
                            ? 'border-blue-600 bg-blue-50'
                            : 'border-gray-300 hover:border-blue-500 hover:bg-blue-50'
                        }`}
                      >
                        <div className="text-sm font-medium text-gray-800">
                          {product}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 3: Coverage Selection */}
              {step === 3 && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    담보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    <div>보험사: <strong>{selectedCompany}</strong></div>
                    <div>상품: <strong>{selectedProduct}</strong></div>
                  </div>
                  <div className="space-y-2">
                    {coverages.map((coverage, index) => (
                      <button
                        key={index}
                        onClick={() => handleCoverageSelect(coverage)}
                        className={`w-full px-3 py-2 border-2 rounded-md transition-colors text-left ${
                          selectedCoverage?.coverage_name === coverage.coverage_name
                            ? 'border-blue-600 bg-blue-50'
                            : 'border-gray-300 hover:border-blue-500 hover:bg-blue-50'
                        }`}
                      >
                        <div className="text-sm font-medium text-gray-800">
                          {coverage.coverage_name}
                        </div>
                        <div className="text-xs text-gray-600 mt-0.5">
                          보장금액: {formatAmount(coverage.benefit_amount)}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 4: Info Type Selection */}
              {step === 4 && !preselectedInfoType && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    조회할 정보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    <div>보험사: <strong>{selectedCompany}</strong></div>
                    <div>상품: <strong>{selectedProduct}</strong></div>
                    <div>담보: <strong>{selectedCoverage?.coverage_name}</strong></div>
                  </div>
                  <div className="space-y-2">
                    {INFO_TYPES.map((infoType) => (
                      <button
                        key={infoType.id}
                        onClick={() => handleInfoTypeSelect(infoType)}
                        className={`w-full px-3 py-3 border-2 rounded-md transition-colors text-left ${
                          selectedInfoType?.id === infoType.id
                            ? 'border-blue-600 bg-blue-50'
                            : 'border-gray-300 hover:border-blue-500 hover:bg-blue-50'
                        }`}
                      >
                        <div className="text-sm font-medium text-gray-800">
                          {infoType.label}
                        </div>
                        <div className="text-xs text-gray-600 mt-0.5">
                          {infoType.description}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-4 py-3 flex justify-between flex-shrink-0 border-t border-gray-200">
          <button
            onClick={step === 1 ? onClose : handleBack}
            className="px-4 py-1.5 text-sm text-gray-700 hover:text-gray-900 transition-colors"
            disabled={loading}
          >
            {step === 1 ? '취소' : '이전'}
          </button>
          {/* Show submit button on step 3 (when preselected) or step 4 */}
          {step >= 3 && (
            <button
              onClick={handleSubmit}
              disabled={!selectedCompany || !selectedProduct || !selectedCoverage || !selectedInfoType || loading}
              className="px-5 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              조회하기
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default InfoQueryBuilder;
