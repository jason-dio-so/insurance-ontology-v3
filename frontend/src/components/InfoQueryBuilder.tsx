import React, { useState, useEffect } from 'react';
import { getCompanies, getCompanyProducts, getProductCoverages, getAllCoverages, getErrorMessage, Coverage, Company } from '../services/api';

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
  const [companies, setCompanies] = useState<Company[]>([]);

  // 다중 선택 모드
  const [selectedCompanies, setSelectedCompanies] = useState<Company[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [isCompareMode, setIsCompareMode] = useState(false);

  // 단일 선택 모드 (기존)
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [products, setProducts] = useState<string[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>('');

  // 공통
  const [coverages, setCoverages] = useState<Coverage[]>([]);
  const [allCoverageNames, setAllCoverageNames] = useState<string[]>([]);
  const [selectedCoverage, setSelectedCoverage] = useState<Coverage | null>(null);
  const [selectedCoverageName, setSelectedCoverageName] = useState<string>('');
  const [coverageSearch, setCoverageSearch] = useState('');
  const [selectedInfoType, setSelectedInfoType] = useState<InfoType | null>(null);
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
      setError(getErrorMessage(err));
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
      setError(getErrorMessage(err));
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
      setError(getErrorMessage(err));
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadAllCoverages = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getAllCoverages();
      setAllCoverageNames(result.coverages);
    } catch (err) {
      setError(getErrorMessage(err));
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 재시도 핸들러
  const handleRetry = () => {
    setError('');
    if (step === 1) {
      loadCompanies();
    } else if (step === 2 && !isCompareMode && selectedCompany) {
      loadProducts(selectedCompany.name);
    } else if (step === 2 && isCompareMode) {
      loadAllCoverages();
    } else if (step === 3 && !isCompareMode && selectedCompany && selectedProduct) {
      loadProductCoverages(selectedCompany.name, selectedProduct);
    }
  };

  // 전체 선택 토글
  const handleSelectAllToggle = () => {
    if (selectAll) {
      setSelectAll(false);
      setSelectedCompanies([]);
    } else {
      setSelectAll(true);
      setSelectedCompanies([...companies]);
    }
  };

  // 개별 회사 체크박스 토글
  const handleCompanyToggle = (company: Company) => {
    const isSelected = selectedCompanies.some(c => c.name === company.name);
    if (isSelected) {
      setSelectedCompanies(selectedCompanies.filter(c => c.name !== company.name));
      setSelectAll(false);
    } else {
      const newSelected = [...selectedCompanies, company];
      setSelectedCompanies(newSelected);
      if (newSelected.length === companies.length) {
        setSelectAll(true);
      }
    }
  };

  // 단일 회사 선택 (기존 방식)
  const handleSingleCompanySelect = async (company: Company) => {
    setSelectedCompany(company);
    setIsCompareMode(false);
    await loadProducts(company.name);
    setStep(2);
  };

  // 다중 선택 확정 (비교 모드)
  const handleCompareSelect = async () => {
    if (selectedCompanies.length < 2) {
      setError('비교하려면 2개 이상의 보험사를 선택하세요.');
      return;
    }
    setIsCompareMode(true);
    await loadAllCoverages();
    setStep(2); // 비교 모드에서는 step 2가 담보 선택
  };

  const handleProductSelect = async (product: string) => {
    setSelectedProduct(product);
    if (selectedCompany) {
      await loadProductCoverages(selectedCompany.name, product);
    }
    setStep(3);
  };

  const handleCoverageSelect = (coverage: Coverage) => {
    setSelectedCoverage(coverage);
    if (!preselectedInfoType) {
      setStep(4);
    }
  };

  // 비교 모드에서 담보명 선택
  const handleCoverageNameSelect = (coverageName: string) => {
    setSelectedCoverageName(coverageName);
    if (!preselectedInfoType) {
      setStep(3); // 비교 모드에서는 step 3이 정보 유형 선택
    }
  };

  const handleInfoTypeSelect = (infoType: InfoType) => {
    setSelectedInfoType(infoType);
  };

  const handleSubmit = () => {
    if (isCompareMode) {
      // 비교 모드 쿼리 생성
      if (!selectedCoverageName || !selectedInfoType) {
        setError('모든 항목을 선택해주세요.');
        return;
      }

      const companyNames = selectAll
        ? '전체 보험사'
        : selectedCompanies.map(c => c.displayName).join(', ');

      const queryTemplates: Record<string, string> = {
        'coverage-start-date': `${companyNames}의 ${selectedCoverageName} 보장개시일을 비교해주세요`,
        'coverage-limit': `${companyNames}의 ${selectedCoverageName} 보장한도를 비교해주세요`,
        'enrollment-age': `${companyNames}의 ${selectedCoverageName} 가입나이를 비교해주세요`,
        exclusions: `${companyNames}의 ${selectedCoverageName} 면책사항을 비교해주세요`,
        'renewal-info': `${companyNames}의 ${selectedCoverageName} 갱신조건을 비교해주세요`,
      };

      const query = queryTemplates[selectedInfoType.id];
      onQuerySubmit(query, `compare-${selectedInfoType.id}`);
      onClose();
    } else {
      // 단일 조회 모드 (기존)
      if (!selectedCompany || !selectedProduct || !selectedCoverage || !selectedInfoType) {
        setError('모든 항목을 선택해주세요.');
        return;
      }

      const companyDisplayName = selectedCompany.displayName;
      const queryTemplates: Record<string, string> = {
        'coverage-start-date': `${companyDisplayName} ${selectedCoverage.coverage_name}의 보장개시일은 언제인가요?`,
        'coverage-limit': `${companyDisplayName} ${selectedCoverage.coverage_name}의 보장한도는 어떻게 되나요?`,
        'enrollment-age': `${companyDisplayName} ${selectedCoverage.coverage_name}는 몇 세까지 가입할 수 있나요?`,
        exclusions: `${companyDisplayName} ${selectedCoverage.coverage_name}의 면책사항은 무엇인가요?`,
        'renewal-info': `${companyDisplayName} ${selectedCoverage.coverage_name}는 갱신형인가요? 감액비율은 얼마인가요?`,
      };

      const query = queryTemplates[selectedInfoType.id];
      onQuerySubmit(query, selectedInfoType.id);
      onClose();
    }
  };

  const handleBack = () => {
    if (isCompareMode) {
      if (step === 2) {
        setSelectedCompanies([]);
        setSelectAll(false);
        setIsCompareMode(false);
        setStep(1);
      } else if (step === 3) {
        setSelectedCoverageName('');
        setStep(2);
      }
    } else {
      if (step === 2) {
        setSelectedCompany(null);
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
    }
  };

  const formatAmount = (amount: number | null) => {
    if (!amount) return 'N/A';
    return `${amount.toLocaleString()}원`;
  };

  // 담보 검색 필터링
  const filteredCoverages = coverageSearch
    ? allCoverageNames.filter(name => name.toLowerCase().includes(coverageSearch.toLowerCase()))
    : allCoverageNames;

  // 진행 단계 계산
  const getSteps = () => {
    if (isCompareMode) {
      return preselectedInfoType ? ['회사', '담보'] : ['회사', '담보', '정보'];
    } else {
      return preselectedInfoType ? ['회사', '상품', '담보'] : ['회사', '상품', '담보', '정보'];
    }
  };

  const steps = getSteps();

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-blue-600 text-white px-4 py-3 flex justify-between items-center flex-shrink-0">
          <h2 className="text-lg font-bold">
            {isCompareMode ? '보험사 비교 조회' : '상품/담보 정보 조회'}
          </h2>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-200 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Progress Steps */}
        <div className="bg-gray-50 px-4 py-2 flex-shrink-0 border-b border-gray-200">
          <div className="flex items-center justify-center gap-2 text-sm">
            {steps.map((label, idx) => (
              <React.Fragment key={idx}>
                <div className="flex items-center gap-1">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                      step > idx ? 'bg-blue-600 text-white' : step === idx + 1 ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <span className={step >= idx + 1 ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                    {label}
                  </span>
                </div>
                {idx < steps.length - 1 && (
                  <div className={`w-8 h-0.5 ${step > idx + 1 ? 'bg-blue-600' : 'bg-gray-300'}`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto flex-1">
          {error && (
            <div className="mb-4 p-3 bg-red-100 rounded flex items-center justify-between">
              <div className="flex items-center gap-2 text-red-700">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{error}</span>
              </div>
              <button
                onClick={handleRetry}
                className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
              >
                다시 시도
              </button>
            </div>
          )}

          {loading ? (
            <div className="flex flex-col justify-center items-center py-12 gap-3">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <span className="text-gray-500 text-sm">
                {step === 1 && '보험사 목록을 불러오는 중...'}
                {step === 2 && !isCompareMode && '상품 목록을 불러오는 중...'}
                {step === 2 && isCompareMode && '담보 목록을 불러오는 중...'}
                {step === 3 && !isCompareMode && '담보 목록을 불러오는 중...'}
              </span>
            </div>
          ) : (
            <>
              {/* Step 1: Company Selection */}
              {step === 1 && (
                <div>
                  <h3 className="text-base font-bold mb-3 text-gray-800">
                    보험사를 선택하세요
                  </h3>

                  {/* 비교 모드 선택 */}
                  <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectAll}
                        onChange={handleSelectAllToggle}
                        className="w-4 h-4 text-blue-600 rounded"
                      />
                      <span className="font-medium text-blue-800">전체 보험사 비교</span>
                    </label>
                    <p className="text-xs text-blue-600 mt-1 ml-6">
                      체크하면 모든 보험사의 담보를 비교할 수 있습니다
                    </p>
                  </div>

                  {/* 개별 선택 (체크박스) */}
                  <div className="grid grid-cols-4 gap-2 mb-4">
                    {companies.map((company) => {
                      const isChecked = selectedCompanies.some(c => c.name === company.name);
                      return (
                        <label
                          key={company.name}
                          className={`px-2 py-2.5 border-2 rounded-md cursor-pointer transition-colors text-center text-sm font-medium ${
                            isChecked
                              ? 'border-blue-500 bg-blue-50 text-blue-800'
                              : 'border-gray-300 text-gray-800 hover:border-blue-300'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleCompanyToggle(company)}
                            className="sr-only"
                          />
                          <span className="flex items-center justify-center gap-1">
                            {isChecked && (
                              <svg className="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                            {company.displayName}
                          </span>
                        </label>
                      );
                    })}
                  </div>

                  {/* 선택된 회사 수 표시 및 다음 버튼 */}
                  {selectedCompanies.length > 0 && (
                    <div className="mt-4">
                      <div className="text-sm text-gray-600 mb-3">
                        선택: {selectedCompanies.length}개 보험사
                        {selectedCompanies.length === 1 && ' (개별 조회)'}
                        {selectedCompanies.length >= 2 && ' (비교 조회)'}
                      </div>
                      <button
                        onClick={selectedCompanies.length === 1
                          ? () => handleSingleCompanySelect(selectedCompanies[0])
                          : handleCompareSelect
                        }
                        className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                      >
                        {selectedCompanies.length === 1
                          ? `${selectedCompanies[0].displayName} 상세 조회`
                          : selectAll
                            ? '전체 보험사 비교하기'
                            : `${selectedCompanies.length}개 보험사 비교하기`
                        }
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Step 2: Product Selection (단일 모드) 또는 Coverage Selection (비교 모드) */}
              {step === 2 && !isCompareMode && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    상품을 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    선택한 보험사: <strong>{selectedCompany?.displayName}</strong>
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
                        <div className="text-sm font-medium text-gray-800">{product}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 2: Coverage Selection (비교 모드) */}
              {step === 2 && isCompareMode && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    비교할 담보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    선택된 보험사: <strong>{selectAll ? '전체' : selectedCompanies.map(c => c.displayName).join(', ')}</strong>
                  </div>

                  {/* 검색 */}
                  <input
                    type="text"
                    placeholder="담보명 검색..."
                    value={coverageSearch}
                    onChange={(e) => setCoverageSearch(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />

                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {filteredCoverages.slice(0, 50).map((coverageName, index) => (
                      <button
                        key={index}
                        onClick={() => handleCoverageNameSelect(coverageName)}
                        className={`w-full px-3 py-2 border rounded-md transition-colors text-left text-sm ${
                          selectedCoverageName === coverageName
                            ? 'border-blue-600 bg-blue-50'
                            : 'border-gray-200 hover:border-blue-500 hover:bg-blue-50'
                        }`}
                      >
                        {coverageName}
                      </button>
                    ))}
                    {filteredCoverages.length > 50 && (
                      <div className="text-sm text-gray-500 text-center py-2">
                        검색어를 입력하여 더 많은 담보를 찾으세요 ({filteredCoverages.length}개 중 50개 표시)
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Step 3: Coverage Selection (단일 모드) */}
              {step === 3 && !isCompareMode && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    담보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    <div>보험사: <strong>{selectedCompany?.displayName}</strong></div>
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
                        <div className="text-sm font-medium text-gray-800">{coverage.coverage_name}</div>
                        <div className="text-xs text-gray-600 mt-0.5">
                          보장금액: {formatAmount(coverage.benefit_amount)}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 3: Info Type Selection (비교 모드) */}
              {step === 3 && isCompareMode && !preselectedInfoType && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    비교할 정보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    <div>보험사: <strong>{selectAll ? '전체' : selectedCompanies.map(c => c.displayName).join(', ')}</strong></div>
                    <div>담보: <strong>{selectedCoverageName}</strong></div>
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
                        <div className="text-sm font-medium text-gray-800">{infoType.label}</div>
                        <div className="text-xs text-gray-600 mt-0.5">{infoType.description}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 4: Info Type Selection (단일 모드) */}
              {step === 4 && !isCompareMode && !preselectedInfoType && (
                <div>
                  <h3 className="text-base font-bold mb-2 text-gray-800">
                    조회할 정보를 선택하세요
                  </h3>
                  <div className="text-xs text-gray-600 mb-3">
                    <div>보험사: <strong>{selectedCompany?.displayName}</strong></div>
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
                        <div className="text-sm font-medium text-gray-800">{infoType.label}</div>
                        <div className="text-xs text-gray-600 mt-0.5">{infoType.description}</div>
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

          {/* 조회하기 버튼 */}
          {((isCompareMode && step >= 2 && selectedCoverageName && selectedInfoType) ||
            (!isCompareMode && step >= 3 && selectedCoverage && selectedInfoType)) && (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-5 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isCompareMode ? '비교하기' : '조회하기'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default InfoQueryBuilder;
