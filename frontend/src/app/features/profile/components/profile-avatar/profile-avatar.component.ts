import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-profile-avatar',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile-avatar.component.html',
  styleUrl: './profile-avatar.component.scss',
})
export class ProfileAvatarComponent {
  @Input() previewUrl: string | null = null;
  @Input() persistedUrl: string | null = null;
  @Output() fileSelected = new EventEmitter<File>();
  @Output() reset = new EventEmitter<void>();

  get displaySrc(): string | null {
    return this.previewUrl ?? this.persistedUrl ?? null;
  }

  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  triggerFileInput(): void {
    this.fileInput.nativeElement.click();
  }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.fileSelected.emit(input.files[0]);
      input.value = '';
    }
  }

  onReset(): void {
    this.reset.emit();
  }
}
