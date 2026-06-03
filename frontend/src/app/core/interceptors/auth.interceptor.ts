import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { AuthStorageService } from '../services/auth-storage.service';
import { ModalService } from '../services/modal.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const storage = inject(AuthStorageService);
  const modalService = inject(ModalService);

  const token = storage.getToken();
  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: unknown) => {
      if (
        err instanceof HttpErrorResponse &&
        err.status === 401 &&
        storage.isAuthenticated()
      ) {
        modalService.show('session-expired');
      }
      return throwError(() => err);
    }),
  );
};
