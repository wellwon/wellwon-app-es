
import Navigation from "@/components/shared/Navigation";
import FinancingHero from "@/components/financing/FinancingHero";
import FinancingProblems from "@/components/financing/FinancingProblems";
import FinancingSolution from "@/components/financing/FinancingSolution";
import FinancingCalculator from "@/components/financing/FinancingCalculator";
import FinancingTestimonials from "@/components/financing/FinancingTestimonials";
import FinancingFAQ from "@/components/financing/FinancingFAQ";
import FinancingCTA from "@/components/financing/FinancingCTA";
import FinancingContact from "@/components/financing/FinancingContact";
import Footer from "@/components/shared/Footer";

const Version3 = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-gray via-medium-gray to-dark-gray overflow-hidden">
      <Navigation />
      <FinancingHero />
      <FinancingProblems />
      <FinancingSolution />
      <FinancingCalculator />
      <FinancingTestimonials />
      <FinancingFAQ />
      <FinancingCTA />
      <FinancingContact />
      <Footer />
    </div>
  );
};

export default Version3;
