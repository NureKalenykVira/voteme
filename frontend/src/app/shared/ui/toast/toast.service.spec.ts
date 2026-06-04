import { TestBed } from '@angular/core/testing';
import { ToastService } from './toast.service';

describe('ToastService', () => {
  let service: ToastService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [ToastService] });
    service = TestBed.inject(ToastService);
  });

  it('starts with an empty toast list', () => {
    expect(service.toasts()).toEqual([]);
  });

  it('success() pushes a toast of type "success"', () => {
    service.success('saved');
    const toasts = service.toasts();
    expect(toasts.length).toBe(1);
    expect(toasts[0].type).toBe('success');
    expect(toasts[0].message).toBe('saved');
  });

  it('error() pushes a toast of type "error"', () => {
    service.error('boom');
    expect(service.toasts()[0].type).toBe('error');
  });

  it('info() pushes a toast of type "info"', () => {
    service.info('fyi');
    expect(service.toasts()[0].type).toBe('info');
  });

  it('assigns unique incrementing ids to consecutive toasts', () => {
    service.info('a');
    service.info('b');
    const [a, b] = service.toasts();
    expect(a.id).not.toBe(b.id);
  });

  it('dismiss(id) removes the matching toast', () => {
    service.info('a');
    const id = service.toasts()[0].id;
    service.dismiss(id);
    expect(service.toasts()).toEqual([]);
  });

  it('auto-removes a toast after the duration elapses', () => {
    vi.useFakeTimers();
    try {
      service.show('temp', 'info', 3000);
      expect(service.toasts().length).toBe(1);
      vi.advanceTimersByTime(2999);
      expect(service.toasts().length).toBe(1);
      vi.advanceTimersByTime(1);
      expect(service.toasts().length).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
