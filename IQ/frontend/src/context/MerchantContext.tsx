import React, { createContext, useContext, useState } from 'react';

interface MerchantContextValue {
  merchantId: string;
  merchantName: string;
  merchantMid: string;
  setMerchant: (id: string, name: string, mid: string) => void;
}

const MerchantContext = createContext<MerchantContextValue>({
  merchantId: '',
  merchantName: '',
  merchantMid: '',
  setMerchant: () => {},
});

export function MerchantProvider({ children }: { children: React.ReactNode }) {
  const [merchantId, setMerchantId] = useState('');
  const [merchantName, setMerchantName] = useState('');
  const [merchantMid, setMerchantMid] = useState('');

  const setMerchant = (id: string, name: string, mid: string) => {
    setMerchantId(id);
    setMerchantName(name);
    setMerchantMid(mid);
  };

  return (
    <MerchantContext.Provider value={{ merchantId, merchantName, merchantMid, setMerchant }}>
      {children}
    </MerchantContext.Provider>
  );
}

export const useMerchant = () => useContext(MerchantContext);
