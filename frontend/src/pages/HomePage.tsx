
import { memo } from "react";
import Navigation from "@/components/shared/Navigation";
import RoadmapSection from "@/components/RoadmapSection";
import TransportMarquee from "@/components/TransportMarquee";
import ServicesGrid from "@/components/ServicesGrid";
import Footer from "@/components/shared/Footer";
import ContactForm from "@/components/ContactForm";
import PlatformShowcase from "@/components/PlatformShowcase";

const HomePage = memo(() => {
  const handleContactClick = () => {
    document.getElementById('contacts')?.scrollIntoView({
      behavior: 'smooth'
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-gray via-medium-gray to-dark-gray pt-24">
      <Navigation />
      
      {/* Platform Showcase Section */}
      <PlatformShowcase />

      {/* Transport Marquee */}
      <TransportMarquee />

      {/* Roadmap Section */}
      <RoadmapSection />

      {/* Services Grid */}
      <section id="services">
        <ServicesGrid />
      </section>

      {/* About Section */}
      <section id="about" className="py-32 px-6 lg:px-12 bg-medium-gray border-t border-light-gray/20">
        <div className="max-w-7xl mx-auto text-center">
          <h2 className="text-5xl lg:text-6xl font-black mb-8 text-white">
            О нас
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
            WellWon — это современная торговая компания, которая помогает бизнесу найти что продать, 
            где купить, поддерживает финансами, привозит, растамаживает, оформляет документы и помогает продать.
          </p>
        </div>
      </section>

      {/* Contact Form Section */}
      <ContactForm />

      {/* Footer */}
      <Footer />
    </div>
  );
});

HomePage.displayName = 'HomePage';

export default HomePage;
