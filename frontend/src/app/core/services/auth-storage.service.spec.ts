import { TestBed } from '@angular/core/testing';
import { AuthStorageService } from './auth-storage.service';
import { Role } from '../../features/auth/models/auth.models';

const STORAGE_KEY = 'auth_token';

// Build a JWT-like token: header.payload.signature with a base64url payload.
function makeToken(payload: Record<string, unknown>): string {
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.sig`;
}

// The service reads localStorage at construction, so seed BEFORE injecting.
function createService(): AuthStorageService {
  TestBed.configureTestingModule({ providers: [AuthStorageService] });
  return TestBed.inject(AuthStorageService);
}

describe('AuthStorageService', () => {
  afterEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
  });

  describe('token persistence', () => {
    it('setToken() stores the token in localStorage and exposes it via getToken()', () => {
      localStorage.clear();
      const service = createService();
      const token = makeToken({ role: 'voter', sub: 'u1' });
      service.setToken(token);
      expect(localStorage.getItem(STORAGE_KEY)).toBe(token);
      expect(service.getToken()).toBe(token);
    });

    it('clearToken() removes the token from localStorage', () => {
      const token = makeToken({ role: 'voter', sub: 'u1' });
      localStorage.setItem(STORAGE_KEY, token);
      const service = createService();
      service.clearToken();
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
      expect(service.getToken()).toBeNull();
    });

    it('initializes getToken() from localStorage present at construction', () => {
      const token = makeToken({ role: 'organizer', sub: 'u2' });
      localStorage.setItem(STORAGE_KEY, token);
      const service = createService();
      expect(service.getToken()).toBe(token);
    });
  });

  describe('isAuthenticated (computed signal)', () => {
    it('is false when no token exists', () => {
      localStorage.clear();
      const service = createService();
      expect(service.isAuthenticated()).toBe(false);
    });

    it('becomes true after setToken()', () => {
      localStorage.clear();
      const service = createService();
      service.setToken(makeToken({ role: 'voter' }));
      expect(service.isAuthenticated()).toBe(true);
    });

    it('becomes false after clearToken()', () => {
      localStorage.setItem(STORAGE_KEY, makeToken({ role: 'voter' }));
      const service = createService();
      expect(service.isAuthenticated()).toBe(true);
      service.clearToken();
      expect(service.isAuthenticated()).toBe(false);
    });
  });

  describe('getRole()', () => {
    const roles: Role[] = ['global_admin', 'organizer', 'voter', 'auditor'];
    roles.forEach(role => {
      it(`extracts "${role}" from the JWT payload`, () => {
        localStorage.setItem(STORAGE_KEY, makeToken({ role, sub: 'x' }));
        const service = createService();
        expect(service.getRole()).toBe(role);
      });
    });

    it('returns null when no token is present', () => {
      localStorage.clear();
      const service = createService();
      expect(service.getRole()).toBeNull();
    });

    it('returns null for a malformed token', () => {
      localStorage.setItem(STORAGE_KEY, 'not-a-jwt');
      const service = createService();
      expect(service.getRole()).toBeNull();
    });

    it('returns null when payload has no role claim', () => {
      localStorage.setItem(STORAGE_KEY, makeToken({ sub: 'x' }));
      const service = createService();
      expect(service.getRole()).toBeNull();
    });
  });

  describe('getCurrentUserId()', () => {
    it('extracts sub from the JWT payload', () => {
      localStorage.setItem(STORAGE_KEY, makeToken({ role: 'voter', sub: 'user-42' }));
      const service = createService();
      expect(service.getCurrentUserId()).toBe('user-42');
    });

    it('returns null when no token is present', () => {
      localStorage.clear();
      const service = createService();
      expect(service.getCurrentUserId()).toBeNull();
    });

    it('returns null for a malformed token', () => {
      localStorage.setItem(STORAGE_KEY, 'broken.token');
      const service = createService();
      expect(service.getCurrentUserId()).toBeNull();
    });
  });
});
