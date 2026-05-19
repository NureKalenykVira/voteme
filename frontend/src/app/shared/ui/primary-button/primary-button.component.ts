import {
  ChangeDetectionStrategy,
  Component,
  Input,
} from '@angular/core';

@Component({
  selector: 'ui-primary-button',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<button [type]="type" [disabled]="disabled" class="btn"><ng-content /></button>`,
  styleUrl: './primary-button.component.scss',
})
export class PrimaryButtonComponent {
  @Input() type: 'submit' | 'button' = 'button';
  @Input() disabled = false;
}
