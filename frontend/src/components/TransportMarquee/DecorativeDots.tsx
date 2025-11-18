
const DecorativeDots = () => (
  <>
    <div className="absolute top-1/2 left-8 w-2 h-2 bg-accent-red/50 rounded-full transform -translate-y-1/2 animate-pulse"></div>
    <div 
      className="absolute top-1/2 right-8 w-2 h-2 bg-accent-red/50 rounded-full transform -translate-y-1/2 animate-pulse"
      style={{ animationDelay: '1s' }}
    ></div>
  </>
);

export default DecorativeDots;
