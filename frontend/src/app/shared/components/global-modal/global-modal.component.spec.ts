import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Location } from '@angular/common';
import { provideTranslateService } from '@ngx-translate/core';
import { GlobalModalComponent } from './global-modal.component';
import { ModalService } from '../../../core/services/modal.service';
import { AuthStorageService } from '../../../core/services/auth-storage.service';

describe('GlobalModalComponent', () => {
  let modal: ModalService;
  let auth: { clearToken: ReturnType<typeof vi.fn> };
  let router: { navigate: ReturnType<typeof vi.fn> };
  let location: { back: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    auth = { clearToken: vi.fn() };
    router = { navigate: vi.fn() };
    location = { back: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [GlobalModalComponent],
      providers: [
        ModalService,
        provideTranslateService(),
        { provide: AuthStorageService, useValue: auth },
        { provide: Router, useValue: router },
        { provide: Location, useValue: location },
      ],
    }).compileComponents();

    modal = TestBed.inject(ModalService);
  });

  function create() {
    const fixture = TestBed.createComponent(GlobalModalComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('should create', () => {
    expect(create().componentInstance).toBeTruthy();
  });

  it('renders nothing when activeModal is null', () => {
    const fixture = create();
    expect((fixture.nativeElement as HTMLElement).querySelector('.gm-overlay')).toBeNull();
  });

  it('shows session-expired content when activeModal = "session-expired"', () => {
    modal.show('session-expired');
    const fixture = create();
    const html = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect((fixture.nativeElement as HTMLElement).querySelector('.gm-overlay')).not.toBeNull();
    expect(html).toContain('globalModal.sessionExpiredTitle');
    expect(html).toContain('globalModal.login');
  });

  it('shows access-denied content when activeModal = "forbidden"', () => {
    modal.show('forbidden');
    const fixture = create();
    const html = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(html).toContain('globalModal.accessDeniedTitle');
    expect(html).toContain('globalModal.goBack');
  });

  it('session-expired login button clears token, closes modal and navigates to login', () => {
    modal.show('session-expired');
    const fixture = create();
    const btn = (fixture.nativeElement as HTMLElement).querySelector('.gm-btn') as HTMLButtonElement;
    btn.click();
    expect(auth.clearToken).toHaveBeenCalled();
    expect(modal.activeModal()).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/auth/login']);
  });

  it('forbidden go-back button closes modal and calls location.back()', () => {
    modal.show('forbidden');
    const fixture = create();
    const btn = (fixture.nativeElement as HTMLElement).querySelector('.gm-btn') as HTMLButtonElement;
    btn.click();
    expect(modal.activeModal()).toBeNull();
    expect(location.back).toHaveBeenCalled();
  });
});
