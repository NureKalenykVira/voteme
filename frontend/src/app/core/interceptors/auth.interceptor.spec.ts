import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { authInterceptor } from './auth.interceptor';
import { AuthStorageService } from '../services/auth-storage.service';
import { ModalService } from '../services/modal.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let storage: {
    getToken: ReturnType<typeof vi.fn>;
    isAuthenticated: ReturnType<typeof vi.fn>;
  };
  let modal: { show: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    storage = { getToken: vi.fn(), isAuthenticated: vi.fn() };
    modal = { show: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStorageService, useValue: storage },
        { provide: ModalService, useValue: modal },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('passes the request through without Authorization header when there is no token', () => {
    storage.getToken.mockReturnValue(null);
    http.get('/api/x').subscribe();
    const req = httpMock.expectOne('/api/x');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('adds "Authorization: Bearer <token>" when a token exists', () => {
    storage.getToken.mockReturnValue('abc.def.ghi');
    http.get('/api/x').subscribe();
    const req = httpMock.expectOne('/api/x');
    expect(req.request.headers.get('Authorization')).toBe('Bearer abc.def.ghi');
    req.flush({});
  });

  it('shows the session-expired modal on a 401 when authenticated', () => {
    storage.getToken.mockReturnValue('abc.def.ghi');
    storage.isAuthenticated.mockReturnValue(true);
    http.get('/api/x').subscribe({ error: () => {} });
    httpMock.expectOne('/api/x').flush('nope', { status: 401, statusText: 'Unauthorized' });
    expect(modal.show).toHaveBeenCalledWith('session-expired');
  });

  it('does NOT show the modal on a 401 when not authenticated', () => {
    storage.getToken.mockReturnValue(null);
    storage.isAuthenticated.mockReturnValue(false);
    http.get('/api/x').subscribe({ error: () => {} });
    httpMock.expectOne('/api/x').flush('nope', { status: 401, statusText: 'Unauthorized' });
    expect(modal.show).not.toHaveBeenCalled();
  });

  it('does NOT show the modal on a non-401 error', () => {
    storage.getToken.mockReturnValue('abc.def.ghi');
    storage.isAuthenticated.mockReturnValue(true);
    http.get('/api/x').subscribe({ error: () => {} });
    httpMock.expectOne('/api/x').flush('err', { status: 500, statusText: 'Server Error' });
    expect(modal.show).not.toHaveBeenCalled();
  });
});
