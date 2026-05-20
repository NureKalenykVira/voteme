import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-activity-link-button',
  standalone: true,
  imports: [RouterModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './activity-link-button.component.html',
  styleUrl: './activity-link-button.component.scss',
})
export class ActivityLinkButtonComponent {
  @Input() label: string = '';
  @Input() routerLink: string = '/home';
}
