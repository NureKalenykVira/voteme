import { Injectable, inject, signal } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';

export type AppLang = 'uk' | 'en';

const LANG_STORAGE_KEY = 'lang';
const DEFAULT_LANG: AppLang = 'en';
const SUPPORTED_LANGS: readonly AppLang[] = ['uk', 'en'];

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly translate = inject(TranslateService);

  readonly currentLang = signal<AppLang>(DEFAULT_LANG);

  init(): void {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    const lang = this.normalize(stored);
    this.apply(lang);
  }

  setLang(lang: AppLang): void {
    if (lang === this.currentLang()) return;
    this.apply(lang);
  }

  toggle(): void {
    this.setLang(this.currentLang() === 'uk' ? 'en' : 'uk');
  }

  private apply(lang: AppLang): void {
    this.translate.use(lang);
    localStorage.setItem(LANG_STORAGE_KEY, lang);
    this.currentLang.set(lang);
  }

  private normalize(value: string | null): AppLang {
    return SUPPORTED_LANGS.includes(value as AppLang) ? (value as AppLang) : DEFAULT_LANG;
  }
}
