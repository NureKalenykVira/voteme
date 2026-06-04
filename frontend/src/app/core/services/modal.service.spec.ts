import { TestBed } from '@angular/core/testing';
import { ModalService } from './modal.service';

describe('ModalService', () => {
  let service: ModalService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [ModalService] });
    service = TestBed.inject(ModalService);
  });

  it('initial activeModal state is null', () => {
    expect(service.activeModal()).toBeNull();
  });

  it('show("session-expired") sets the activeModal signal', () => {
    service.show('session-expired');
    expect(service.activeModal()).toBe('session-expired');
  });

  it('show("forbidden") sets the activeModal signal', () => {
    service.show('forbidden');
    expect(service.activeModal()).toBe('forbidden');
  });

  it('close() clears the activeModal signal', () => {
    service.show('session-expired');
    service.close();
    expect(service.activeModal()).toBeNull();
  });
});
