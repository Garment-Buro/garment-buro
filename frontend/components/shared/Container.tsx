import React from 'react';

interface ContainerProps {
  children: React.ReactNode;
  size?: '1200' | '1100' | '1000' | '700' | 'full';
  className?: string;
}

export const Container: React.FC<ContainerProps> = ({
  children,
  size = '1200',
  className = ''
}) => {
  const maxWidthClass = {
    '1200': 'max-w-(--spacing-wrapper-1200)',
    '1100': 'max-w-(--spacing-wrapper-1100)',
    '1000': 'max-w-(--spacing-wrapper-1000)',
    '700': 'max-w-(--spacing-wrapper-700)',
    'full': 'max-w-full'
  }[size];

  return (
    <div className={`${maxWidthClass} mx-auto px-4 md:px-6 lg:px-8 w-full ${className}`}>
      {children}
    </div>
  );
};
