import React from 'react';

interface TextPageContainerProps {
    children: React.ReactNode;
}

export const TextPageContainer: React.FC<TextPageContainerProps> = ({ children }) => {
    return (
        <div className="w-full flex flex-col items-center">
            {/* 
         Desktop: 150px from header, 880px width, 150px from footer.
         Mobile: 320px width, 50px from top, 120px from footer.
      */}
            <div className="
        w-[320px] mt-[120px] mb-[120px]
        md:w-[880px] md:mt-[150px] md:mb-[150px]
        mx-auto
      ">
                {children}
            </div>
        </div>
    );
};
