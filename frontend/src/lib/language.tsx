import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type Language = 'vi' | 'en';
type LanguageContextValue = { language: Language; setLanguage: (language: Language) => void; t: (vietnamese: string, english: string) => string };
const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => localStorage.getItem('soicterra-language') === 'en' ? 'en' : 'vi');
  const setLanguage = (next: Language) => setLanguageState(next);
  useEffect(() => {
    localStorage.setItem('soicterra-language', language);
    document.documentElement.lang = language;
  }, [language]);
  const value = useMemo(() => ({ language, setLanguage, t: (vi: string, en: string) => language === 'vi' ? vi : en }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error('useLanguage must be used inside LanguageProvider');
  return value;
}
