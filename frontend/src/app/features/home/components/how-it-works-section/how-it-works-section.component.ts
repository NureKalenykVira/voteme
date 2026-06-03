import { NgFor } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import {
  StepCardComponent,
  StepCardVariant,
} from '../../../../shared/ui/step-card/step-card.component';

interface Step {
  step: number;
  title: string;
  description: string;
  variant: StepCardVariant;
}

@Component({
  selector: 'app-how-it-works-section',
  standalone: true,
  imports: [NgFor, RouterLink, StepCardComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './how-it-works-section.component.html',
  styleUrl: './how-it-works-section.component.scss',
})
export class HowItWorksSectionComponent {
  readonly steps: Step[] = [
    { step: 1, title: 'home.hiw.step1.title', description: 'home.hiw.step1.desc', variant: 'white' },
    { step: 2, title: 'home.hiw.step2.title', description: 'home.hiw.step2.desc', variant: 'lime' },
    { step: 3, title: 'home.hiw.step3.title', description: 'home.hiw.step3.desc', variant: 'purple' },
    { step: 4, title: 'home.hiw.step4.title', description: 'home.hiw.step4.desc', variant: 'outlined-dark' },
  ];
}
