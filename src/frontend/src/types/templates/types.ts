import type { FlowType } from "@/types/flow";

export interface NavItem {
  title: string;
  icon: string;
  id: string;
}

export interface Category {
  title: string;
  items: NavItem[];
}

export interface CardData {
  bgImage: string;
  bgHorizontalImage: string;
  icon: string;
  category: string;
  flow: FlowType | undefined;
}

export interface TemplateCategoryProps {
  examples: any[];
  onCardClick: (example: any) => void;
}

export interface TemplateContentProps {
  currentTab: string;
  categories: NavItem[];
  isAdmin?: boolean;
}

export interface TemplateCardComponentProps {
  example: {
    name: string;
    description: string;
    icon?: string;
    id: string;
    gradient?: string;
  };
  onClick: () => void;
  selected?: boolean;
  onSelect?: () => void;
}

export interface NavProps {
  items: NavItem[];
  currentTab: string;
  setCurrentTab: (id: string) => void;
  isAdmin?: boolean;
}

export interface ApiCategory {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string | null;
}
