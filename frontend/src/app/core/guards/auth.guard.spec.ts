import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  CanActivateFn,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { authGuard } from './auth.guard';
import { AuthStorageService } from '../services/auth-storage.service';

function run(state: RouterStateSnapshot): ReturnType<CanActivateFn> {
  return TestBed.runInInjectionContext(() =>
    authGuard({} as ActivatedRouteSnapshot, state),
  );
}

describe('authGuard', () => {
  let auth: { isAuthenticated: ReturnType<typeof vi.fn> };
  let router: Router;

  beforeEach(() => {
    auth = { isAuthenticated: vi.fn() };
    TestBed.configureTestingModule({
      providers: [{ provide: AuthStorageService, useValue: auth }],
    });
    router = TestBed.inject(Router);
  });

  it('returns true for an authenticated user', () => {
    auth.isAuthenticated.mockReturnValue(true);
    const result = run({ url: '/dashboard' } as RouterStateSnapshot);
    expect(result).toBe(true);
  });

  it('returns a UrlTree to /auth/login for an unauthenticated user', () => {
    auth.isAuthenticated.mockReturnValue(false);
    const result = run({ url: '/dashboard' } as RouterStateSnapshot);
    expect(result instanceof UrlTree).toBe(true);
    expect((result as UrlTree).toString()).toContain('/auth/login');
  });

  it('preserves the attempted url as returnUrl query param', () => {
    auth.isAuthenticated.mockReturnValue(false);
    const result = run({ url: '/elections/5' } as RouterStateSnapshot) as UrlTree;
    expect(result.queryParams['returnUrl']).toBe('/elections/5');
  });
});
