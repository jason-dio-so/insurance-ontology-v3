import React from 'react';
import { ComparisonResult } from '../types';

interface ComparisonTableProps {
  data: ComparisonResult[];
}

const ComparisonTable: React.FC<ComparisonTableProps> = ({ data }) => {
  if (!data || data.length === 0) return null;

  return (
    <div className="my-4 overflow-x-auto">
      <table className="min-w-full bg-gray-800 rounded-lg overflow-hidden">
        <thead className="bg-gray-700">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
              회사
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
              상품
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
              담보
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">
              보장금액
            </th>
            {data.some((d) => d.premium) && (
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">
                월보험료
              </th>
            )}
            {data.some((d) => d.notes) && (
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                비고
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700">
          {data.map((row, index) => (
            <tr
              key={index}
              className="hover:bg-gray-750 transition-colors duration-150"
            >
              <td className="px-4 py-3 text-sm text-white font-medium">
                {row.company}
              </td>
              <td className="px-4 py-3 text-sm text-gray-300">
                {row.product}
              </td>
              <td className="px-4 py-3 text-sm text-gray-300">
                {row.coverage}
              </td>
              <td className="px-4 py-3 text-sm text-right text-blue-400 font-medium">
                {row.benefit}
              </td>
              {data.some((d) => d.premium) && (
                <td className="px-4 py-3 text-sm text-right text-green-400">
                  {row.premium || '-'}
                </td>
              )}
              {data.some((d) => d.notes) && (
                <td className="px-4 py-3 text-sm text-gray-400">
                  {row.notes || '-'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ComparisonTable;
