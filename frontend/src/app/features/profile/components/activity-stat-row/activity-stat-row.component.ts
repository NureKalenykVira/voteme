import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-activity-stat-row',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './activity-stat-row.component.html',
  styleUrl: './activity-stat-row.component.scss',
})
export class ActivityStatRowComponent {
  @Input() label: string = '';
  @Input() value: string | number = 0;
}
