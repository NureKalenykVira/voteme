import { ChangeDetectionStrategy, Component } from '@angular/core';
import { FaqBannerComponent } from '../../../../shared/ui/faq-banner/faq-banner.component';

@Component({
  selector: 'app-see-it-in-action-section',
  standalone: true,
  imports: [FaqBannerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './see-it-in-action-section.component.html',
  styleUrl: './see-it-in-action-section.component.scss',
})
export class SeeItInActionSectionComponent {}
