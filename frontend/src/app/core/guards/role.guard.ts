import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthStorageService } from '../services/auth-storage.service';
import { Role } from '../../features/auth/models/auth.models';

export function roleGuard(...allowedRoles: Role[]): CanActivateFn {
  return () => {
    const auth = inject(AuthStorageService);
    const router = inject(Router);

    if (!auth.isAuthenticated()) {
      return router.createUrlTree(['/auth/login']);
    }

    const role = auth.getRole();
    if (role && allowedRoles.includes(role)) {
      return true;
    }

    return router.createUrlTree(['/profile']);
  };
}
