import { Menu, X } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import UTMLink from "./UTMLink";
import ProfileIcon from "./ProfileIcon";
import UniversalProfileDropdown from "./UniversalProfileDropdown";

const Navigation = () => {
  const { user, loading } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const location = useLocation();
  const isHomePage = location.pathname === '/';
  
  const handleLinkClick = () => {
    setIsMenuOpen(false);
    setIsProfileOpen(false);
  };
  
  const handleContactClick = () => {
    if (isHomePage) {
      document.getElementById('contacts')?.scrollIntoView({
        behavior: 'smooth'
      });
    }
  };
  
  return <nav className="fixed top-0 left-0 right-0 z-50 bg-dark-gray">
      <div className="container mx-auto px-6 lg:px-12">
        <div className="flex items-center justify-between h-24">
          <UTMLink to="/" onClick={handleLinkClick} className="flex flex-col leading-tight">
            <div className="text-accent-red text-4xl font-black tracking-tight relative">
              Well<span className="text-white">Won</span>
              <div className="absolute -bottom-1 left-0 w-12 h-0.5 bg-accent-red"></div>
            </div>
          </UTMLink>
          
          <div className="hidden md:flex items-center space-x-10">
            <UTMLink to="/financing" className={`transition-all duration-300 relative group ${location.pathname === '/financing' ? 'text-accent-red' : 'text-gray-300 hover:text-accent-red'}`}>
              Финансирование
              <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
            </UTMLink>
            
            {isHomePage ? (
              <button 
                onClick={() => document.getElementById('services')?.scrollIntoView({ behavior: 'smooth' })} 
                className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group bg-transparent border-none cursor-pointer"
              >
                Услуги
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </button>
            ) : (
              <UTMLink to="/#services" className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group">
                Услуги
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </UTMLink>
            )}
            
            {isHomePage ? (
              <button 
                onClick={() => document.getElementById('about')?.scrollIntoView({ behavior: 'smooth' })} 
                className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group bg-transparent border-none cursor-pointer"
              >
                О нас
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </button>
            ) : (
              <UTMLink to="/#about" className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group">
                О нас
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </UTMLink>
            )}
            
            {isHomePage ? (
              <button 
                onClick={() => document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' })} 
                className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group bg-transparent border-none cursor-pointer"
              >
                Контакты
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </button>
            ) : (
              <UTMLink to="/#contacts" className="text-gray-300 hover:text-accent-red transition-all duration-300 relative group">
                Контакты
                <div className="absolute -bottom-2 left-0 w-0 h-0.5 bg-accent-red group-hover:w-full transition-all duration-300"></div>
              </UTMLink>
            )}
          </div>

          <div className="hidden md:flex items-center space-x-4">
            {user && !loading && (
              <UTMLink
                to="/platform"
                className="bg-accent-red hover:bg-accent-red/90 text-white px-4 py-2 rounded-lg font-medium transition-colors"
              >
                Платформа
              </UTMLink>
            )}
            
            {user && !loading ? (
              <div className="relative">
                <ProfileIcon 
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                  isOpen={isProfileOpen}
                />
                <UniversalProfileDropdown 
                  isOpen={isProfileOpen}
                  onClose={() => setIsProfileOpen(false)}
                />
              </div>
            ) : (
              <>
                <UTMLink
                  to="/auth?mode=login"
                  className="text-gray-300 hover:text-accent-red transition-colors font-medium"
                >
                  Войти
                </UTMLink>
                
                <UTMLink
                  to="/auth?mode=signup"
                  className="bg-medium-gray hover:bg-light-gray text-white px-6 py-2 rounded-lg font-medium transition-colors border border-text-white/20"
                >
                  Начать
                </UTMLink>
              </>
            )}

          </div>

          <button className="md:hidden text-gray-300 transform hover:scale-110 transition-transform" onClick={() => setIsMenuOpen(!isMenuOpen)}>
            {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {isMenuOpen && <div className="md:hidden py-6 animate-fade-in">
            <div className="space-y-4">
              <UTMLink to="/financing" className="block text-gray-300 hover:text-accent-red transition-colors py-2" onClick={handleLinkClick}>
                Финансирование
              </UTMLink>
              
              {isHomePage ? (
                <button 
                  onClick={() => {
                    document.getElementById('services')?.scrollIntoView({ behavior: 'smooth' });
                    handleLinkClick();
                  }} 
                  className="block text-gray-300 hover:text-accent-red transition-colors py-2 bg-transparent border-none cursor-pointer text-left w-full"
                >
                  Услуги
                </button>
              ) : (
                <UTMLink to="/#services" className="block text-gray-300 hover:text-accent-red transition-colors py-2" onClick={handleLinkClick}>
                  Услуги
                </UTMLink>
              )}
              
              {isHomePage ? (
                <button 
                  onClick={() => {
                    document.getElementById('about')?.scrollIntoView({ behavior: 'smooth' });
                    handleLinkClick();
                  }} 
                  className="block text-gray-300 hover:text-accent-red transition-colors py-2 bg-transparent border-none cursor-pointer text-left w-full"
                >
                  О нас
                </button>
              ) : (
                <UTMLink to="/#about" className="block text-gray-300 hover:text-accent-red transition-colors py-2" onClick={handleLinkClick}>
                  О нас
                </UTMLink>
              )}
              
              {isHomePage ? (
                <button 
                  onClick={() => {
                    document.getElementById('contacts')?.scrollIntoView({ behavior: 'smooth' });
                    handleLinkClick();
                  }} 
                  className="block text-gray-300 hover:text-accent-red transition-colors py-2 bg-transparent border-none cursor-pointer text-left w-full"
                >
                  Контакты
                </button>
              ) : (
                <UTMLink to="/#contacts" className="block text-gray-300 hover:text-accent-red transition-colors py-2" onClick={handleLinkClick}>
                  Контакты
                </UTMLink>
              )}
              
              <div className="space-y-3 mt-4">
                {user && !loading ? (
                  <div className="text-center space-y-3">
                    <UTMLink
                      to="/platform"
                      className="block bg-accent-red hover:bg-accent-red/90 text-white px-6 py-2 rounded-lg font-medium transition-colors text-center"
                      onClick={handleLinkClick}
                    >
                      Платформа
                    </UTMLink>
                    
                    <div className="flex items-center justify-center gap-3 py-2">
                      <ProfileIcon 
                        onClick={() => setIsProfileOpen(!isProfileOpen)}
                        isOpen={isProfileOpen}
                      />
                      <span className="text-white text-sm">Авторизован</span>
                    </div>
                    {isProfileOpen && (
                      <UniversalProfileDropdown 
                        isOpen={isProfileOpen}
                        onClose={() => setIsProfileOpen(false)}
                        position="top"
                      />
                    )}
                  </div>
                ) : (
                  <>
                    <UTMLink
                      to="/auth?mode=login"
                      className="block text-gray-300 hover:text-accent-red transition-colors py-2 text-center font-medium"
                      onClick={handleLinkClick}
                    >
                      Войти
                    </UTMLink>
                    
                    <UTMLink
                      to="/auth?mode=signup"
                      className="block bg-accent-red hover:bg-accent-red/90 text-white px-6 py-2 rounded-lg font-medium transition-colors text-center"
                      onClick={handleLinkClick}
                    >
                      Начать
                    </UTMLink>
                  </>
                )}

              </div>
            </div>
          </div>}
      </div>
    </nav>;
};

export default Navigation;
