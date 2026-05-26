import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  EventEmitter,
  inject,
  Input,
  Output,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormGroup } from '@angular/forms';

@Component({
  selector: 'app-voting-option-card',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './voting-option-card.component.html',
  styleUrls: ['./voting-option-card.component.scss'],
})
export class VotingOptionCardComponent {
  private readonly cdr = inject(ChangeDetectorRef);

  @Input({ required: true }) formGroup!: FormGroup;
  @Input() index = 0;
  @Input() canRemove = false;
  @Input() existingPhotoUrl = '';
  @Output() remove = new EventEmitter<void>();
  @Output() photoSelected = new EventEmitter<File | null>();

  photoPreview = '';

  onFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.formGroup.get('photo')?.setValue(file.name);
    const reader = new FileReader();
    reader.onload = (e) => {
      this.photoPreview = e.target?.result as string;
      this.cdr.markForCheck();
    };
    reader.readAsDataURL(file);
    this.photoSelected.emit(file);
  }

  clearPhoto(): void {
    this.photoPreview = '';
    this.existingPhotoUrl = '';
    this.formGroup.get('photo')?.setValue('');
    this.photoSelected.emit(null);
  }
}
