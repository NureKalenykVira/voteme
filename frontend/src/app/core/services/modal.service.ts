import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ModalService {
  readonly activeModal = signal<'session-expired' | 'forbidden' | null>(null);

  show(type: 'session-expired' | 'forbidden'): void {
    this.activeModal.set(type);
  }

  close(): void {
    this.activeModal.set(null);
  }
}
