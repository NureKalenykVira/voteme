import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-profile-field',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile-field.component.html',
  styleUrl: './profile-field.component.scss',
})
export class ProfileFieldComponent {
  @Input() label: string = '';
}
