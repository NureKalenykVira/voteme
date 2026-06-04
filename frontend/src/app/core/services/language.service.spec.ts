import { TestBed } from '@angular/core/testing';
import { TranslateService } from '@ngx-translate/core';
import { LanguageService } from './language.service';

describe('LanguageService', () => {
  let service: LanguageService;
  let translate: { use: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    localStorage.clear();
    translate = { use: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        LanguageService,
        { provide: TranslateService, useValue: translate },
      ],
    });
    service = TestBed.inject(LanguageService);
  });

  afterEach(() => localStorage.clear());

  it('should be created with default lang "en"', () => {
    expect(service).toBeTruthy();
    expect(service.currentLang()).toBe('en');
  });

  describe('init()', () => {
    it('defaults to "en" when localStorage is empty', () => {
      service.init();
      expect(service.currentLang()).toBe('en');
      expect(translate.use).toHaveBeenCalledWith('en');
      expect(localStorage.getItem('lang')).toBe('en');
    });

    it('applies a stored supported lang ("uk")', () => {
      localStorage.setItem('lang', 'uk');
      service.init();
      expect(service.currentLang()).toBe('uk');
      expect(translate.use).toHaveBeenCalledWith('uk');
    });

    it('falls back to "en" for an unsupported stored value', () => {
      localStorage.setItem('lang', 'fr');
      service.init();
      expect(service.currentLang()).toBe('en');
      expect(translate.use).toHaveBeenCalledWith('en');
    });
  });

  describe('setLang()', () => {
    it('switches to "uk": calls translate.use, sets localStorage, updates signal', () => {
      service.setLang('uk');
      expect(translate.use).toHaveBeenCalledWith('uk');
      expect(localStorage.getItem('lang')).toBe('uk');
      expect(service.currentLang()).toBe('uk');
    });

    it('is a no-op when the same lang is already active', () => {
      // default is 'en'
      service.setLang('en');
      expect(translate.use).not.toHaveBeenCalled();
      expect(service.currentLang()).toBe('en');
    });
  });

  describe('toggle()', () => {
    it('switches en -> uk', () => {
      expect(service.currentLang()).toBe('en');
      service.toggle();
      expect(service.currentLang()).toBe('uk');
      expect(translate.use).toHaveBeenCalledWith('uk');
    });

    it('switches uk -> en', () => {
      service.setLang('uk');
      translate.use.mockClear();
      service.toggle();
      expect(service.currentLang()).toBe('en');
      expect(translate.use).toHaveBeenCalledWith('en');
    });
  });

  it('currentLang signal updates reactively across calls', () => {
    const seen: string[] = [];
    seen.push(service.currentLang());
    service.setLang('uk');
    seen.push(service.currentLang());
    service.setLang('en');
    seen.push(service.currentLang());
    expect(seen).toEqual(['en', 'uk', 'en']);
  });
});
