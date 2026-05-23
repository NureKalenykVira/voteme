import { ChangeDetectionStrategy, Component } from '@angular/core';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';
import { HeroSectionComponent } from './components/hero-section/hero-section.component';
import { HowItWorksSectionComponent } from './components/how-it-works-section/how-it-works-section.component';
import { SeeItInActionSectionComponent } from './components/see-it-in-action-section/see-it-in-action-section.component';
import { PricingSectionComponent } from './components/pricing-section/pricing-section.component';
import { ScrollToTopComponent } from '../../shared/ui/scroll-to-top/scroll-to-top.component';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    PublicHeaderComponent,
    HeroSectionComponent,
    HowItWorksSectionComponent,
    SeeItInActionSectionComponent,
    PricingSectionComponent,
    PublicFooterComponent,
    ScrollToTopComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {}
