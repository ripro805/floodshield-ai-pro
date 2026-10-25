'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

type Language = 'en' | 'bn';
type Dictionary = Record<string, string>;

const dictionaries: Record<Language, Dictionary> = {
  en: {
    districtMap: 'District Map', alerts: 'Alerts', reports: 'Reports', hospitalResources: 'Hospital Resources', adminPanel: 'Admin Panel',
    liveAlerts: 'Live Alerts', floodCheck: 'Quick Flood Check', environmental: 'Environmental Monitoring', searchLocation: 'Search district or upazila',
    signIn: 'Sign In', logout: 'Log out', floodShield: 'FloodShield AI',
    hospitalOps: 'Hospital Operations', ngoRelief: 'NGO Relief', fieldOps: 'Field Operations',
    emergencyCommand: 'Emergency Command', citizenReports: 'Citizen Reports', automationEngine: 'Automation Engine',
  },
  bn: {
    districtMap: 'জেলা মানচিত্র', alerts: 'সতর্কতা', reports: 'রিপোর্ট', hospitalResources: 'হাসপাতাল সম্পদ', adminPanel: 'অ্যাডমিন প্যানেল',
    liveAlerts: 'লাইভ সতর্কতা', floodCheck: 'দ্রুত বন্যা পরীক্ষা', environmental: 'পরিবেশ পর্যবেক্ষণ', searchLocation: 'জেলা বা উপজেলা খুঁজুন',
    signIn: 'সাইন ইন', logout: 'লগ আউট', floodShield: 'ফ্লাডশিল্ড AI',
    hospitalOps: 'হাসপাতাল কার্যক্রম', ngoRelief: 'এনজিও ত্রাণ বিতরণ', fieldOps: 'মাঠপর্যায়ের কার্যক্রম',
    emergencyCommand: 'জরুরী কমান্ড সেন্টার', citizenReports: 'নাগরিক রিপোর্ট ও ট্র্যাকিং', automationEngine: 'অটোমেশন ইঞ্জিন',
  },
};

interface LanguageContextValue { language: Language; setLanguage: (language: Language) => void; t: (key: string) => string; }
const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>('en');
  useEffect(() => { const saved = window.localStorage.getItem('floodshield-language'); if (saved === 'bn' || saved === 'en') setLanguageState(saved); }, []);
  const setLanguage = (next: Language) => { setLanguageState(next); window.localStorage.setItem('floodshield-language', next); };
  const value = useMemo(() => ({ language, setLanguage, t: (key: string) => dictionaries[language][key] ?? dictionaries.en[key] ?? key }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside LanguageProvider');
  return context;
}
