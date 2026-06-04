import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { roleGuard } from './role.guard';
import { AuthStorageService } from '../services/auth-storage.service';
import { ModalService } from '../services/modal.service';
import { Role } from '../../features/auth/models/auth.models';

function run(...allowed: Role[]) {
  const guard = roleGuard(...allowed);
  return TestBed.runInInjectionContext(() =>
    guard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
}

describe('roleGuard', () => {
  let auth: {
    isAuthenticated: ReturnType<typeof vi.fn>;
    getRole: ReturnType<typeof vi.fn>;
  };
  let modal: { show: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    auth = { isAuthenticated: vi.fn(), getRole: vi.fn() };
    modal = { show: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthStorageService, useValue: auth },
        { provide: ModalService, useValue: modal },
      ],
    });
  });

  it('returns true when the user has the required role', () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getRole.mockReturnValue('organizer');
    expect(run('organizer')).toBe(true);
    expect(modal.show).not.toHaveBeenCalled();
  });

  it('returns true when the role is one of several allowed roles', () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getRole.mockReturnValue('auditor');
    expect(run('organizer', 'auditor')).toBe(true);
  });

  it('shows the forbidden modal and returns false for the wrong role', () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getRole.mockReturnValue('voter');
    const result = run('organizer');
    expect(result).toBe(false);
    expect(modal.show).toHaveBeenCalledWith('forbidden');
  });

  it('shows the forbidden modal when the role is null', () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getRole.mockReturnValue(null);
    const result = run('organizer');
    expect(result).toBe(false);
    expect(modal.show).toHaveBeenCalledWith('forbidden');
  });

  it('returns a UrlTree to /auth/login for an unauthenticated user', () => {
    auth.isAuthenticated.mockReturnValue(false);
    const result = run('organizer');
    expect(result instanceof UrlTree).toBe(true);
    expect((result as UrlTree).toString()).toContain('/auth/login');
    expect(modal.show).not.toHaveBeenCalled();
  });
});
