from django.http import JsonResponse
from django.shortcuts import render
from django.core.cache import cache
from django.conf import settings
import random
import json
import logging
#import requests
from abc import ABC, abstractmethod
from fuzzywuzzy import process
from typing import Dict, List, Optional, Protocol, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import re

#domain models
@dataclass
class CryptoData:
    """
    Domain model representing cryptocurrency metadata and analytics.

    This class encapsulates both static and dynamic information about a cryptocurrency
    to support chatbot analysis, risk profiling, and data freshness checks.

    Attributes:
        name (str): Name of the cryptocurrency.
        trend (str): Market trend descriptor (e.g., 'bullish', 'bearish', 'stable').
        verdict (str): System or analyst-based conclusion (e.g., 'hold', 'buy').
        advice (str): Text-based advice for users.
        market_cap (str): Market capitalization category (e.g., 'low', 'medium', 'high').
        sustainability_score (float): Score indicating the project's long-term viability.
        last_updated (datetime): Timestamp of the last data refresh.
        price_change_24h (Optional[float]): 24-hour price change percentage.
        tags (List[str]): Custom or system-assigned tags for classification or filtering.
    """

    name: str
    trend: str
    verdict: str
    advice: str
    market_cap: str = "medium"
    sustainability_score: float = 5.0
    last_updated: datetime = field(default_factory=datetime.now)
    price_change_24h: Optional[float] = None
    tags: List[str] = field(default_factory=list)

    @property
    def is_bullish(self) -> bool:
        """
        Determine if the crypto is exhibiting a bullish (positive) trend.

        Returns:
            bool: True if the trend is considered bullish, False otherwise.
        """
        return self.trend in ["bullish", "rising", "pump"]

    @property
    def risk_level(self) -> str:
        """
        Compute a qualitative risk level based on trend and market cap.

        Returns:
            str: Risk level, one of ['low', 'medium', 'high', 'very_high'].
        """
        risk_map = {
            ("bullish", "high"): "low",
            ("rising", "high"): "low",
            ("consolidating", "high"): "medium",
            ("stable", "medium"): "medium",
            ("volatile", "medium"): "high",
            ("bearish", "low"): "very_high",
            ("dump", "low"): "very_high"
        }
        return risk_map.get((self.trend, self.market_cap), "medium")

    @property
    def is_stale(self) -> bool:
        """
        Check if the data is outdated based on a 1-hour freshness window.

        Returns:
            bool: True if the data is older than 1 hour, else False.
        """
        return datetime.now() - self.last_updated > timedelta(hours=1)

    def add_tag(self, tag: str) -> bool:
        """
        Add a unique classification tag to this crypto asset.

        Args:
            tag (str): A short string used to label or filter this crypto.

        Returns:
            bool: True if the tag was added, False if it already existed.
        """
        if tag not in self.tags:
            self.tags.append(tag)
            return True
        return False
    
class ConversationType(Enum):
    """
    Enum defining recognized types of user conversation intents for categorizing chatbot interactions.
    """
    GREETING = "greeting"
    STATUS = "status"
    COMPLIMENT = "compliment"
    QUESTION = "question"
    PORTFOLIO = "portfolio"
    TREND_ANALYSIS = "trend_analysis"
    DEFAULT = "default"

@dataclass
class UsersContext:
    """
    store session-specific data to mantain context during multi-turn conversations.
    Tracks personalization factors such as user preferences, history of messages,
    risk tolerance and recent activity timestamps for more intelligent interactions
    """
    session_id: str
    favorite_coins: List[str] = field(default_factory=list)
    conversation_history: List[str] = field(default_factory=list)
    risk_tolerance: str = "medium" #low, medium, high
    last_activity: datetime = field(default_factory=datetime.now)

    def add_to_history(self, message:str) -> None:
        """Add message to conversation history (keep last 10)"""
        self.conversation_history.append(message)
        if len(self.conversation_history) > 10:
            self.conversation_history.pop(0)
        self.last_activity = datetime.now()


#protocols $$ interfaces
class DataProvider(Protocol):
    """Protocol for data providers"""
    def get_crypto_data(self, coin_name: str) -> Optional[CryptoData]:
        """Get crypto data from provider"""
        ...

    def get_all_coins(self) -> List[str]:
        """Get all available coins"""
        ...

class ResponseGenerator(ABC):
    """Abstract base for response generators"""
    
    @abstractmethod
    def can_handle(self, user_input: str, context: UsersContext) -> bool:
        """Check if this generator can handle the input"""
        ...

    @abstractmethod
    def generate_response(self, user_input: str, context: UsersContext) -> Dict[str, Any]:
        """generate response for the input"""
        ...


class StaticCryptoProvider:
    """Static crypto data provider (fallback)"""
    
    def __init__(self):
        self.crypto_db = {
            "bitcoin": CryptoData(
                name="bitcoin",
                trend="bullish",
                verdict="The OG cryptocurrency. Digital gold that never tarnishes.",
                advice="BTC is your crypto foundation. Stack sats and stay humble.",
                market_cap="high",
                sustainability_score=3.0,
                price_change_24h=2.5,
                tags=["store-of-value", "digital-gold", "layer-1"]
            ),
            "ethereum": CryptoData(
                name="ethereum",
                trend="consolidating",
                verdict="The smart contract pioneer. Still the king of DeFi.",
                advice="ETH powers the decentralized future. Stake it for the long haul.",
                market_cap="high",
                sustainability_score=8.0,
                price_change_24h=1.8,
                tags=["smart-contracts", "defi", "layer-1", "pos"]
            ),
            "dogecoin": CryptoData(
                name="dogecoin",
                trend="volatile",
                verdict="Much wow, such meme. The people's crypto.",
                advice="DOGE is fun money. Only invest your meme budget.",
                market_cap="medium",
                sustainability_score=4.0,
                price_change_24h=-3.2,
                tags=["meme", "payment", "community"]
            ),
            "solana": CryptoData(
                name="solana",
                trend="pump",
                verdict="The Ethereum killer with actual speed. When it works.",
                advice="SOL moves fast and breaks things. High risk, high reward.",
                market_cap="medium",
                sustainability_score=7.0,
                price_change_24h=8.7,
                tags=["layer-1", "fast", "cheap", "defi"]
            ),
            "cardano": CryptoData(
                name="cardano",
                trend="stable",
                verdict="The academic's blockchain. Slow and steady wins the race?",
                advice="ADA is a long-term play. Perfect for patient investors.",
                market_cap="medium",
                sustainability_score=9.0,
                price_change_24h=0.5,
                tags=["academic", "pos", "sustainable", "layer-1"]
            ),
            "chainlink": CryptoData(
                name="chainlink",
                trend="rising",
                verdict="The oracle that connects blockchains to reality.",
                advice="LINK is infrastructure. Not sexy, but essential.",
                market_cap="medium",
                sustainability_score=7.5,
                price_change_24h=4.2,
                tags=["oracle", "infrastructure", "defi"]
            )
        }
    
    def get_crypto_data(self, coin_name: str) -> Optional[CryptoData]:
        return self.crypto_db.get(coin_name.lower())
    
    def get_all_coins(self) -> List[str]:
        return list(self.crypto_db.keys())
    
    def add_crypto(self, crypto_data: CryptoData) -> None:
        """Dynamically add new crypto data"""
        self.crypto_db[crypto_data.name.lower()] = crypto_data


class CachedDataProvider:
    """Wrapper that adds caching functionality to any data provider"""

    def __init__(self, provider: DataProvider, cache_backend=cache, cache_timeout: int = 3600):
        """
        Initialize the CachedDataProvider with a concrete provider & optional cache settings.
        Args:
            provider (DataProvider): The backend provider for crypto data.
            cache_backend: Django-compatible cache backend (default: global "cache")
            cache_timeout (int): Time-to-live for cache entries in seconds
        """
        self.provider = provider
        self.cache = cache_backend
        self.cache_timeout = cache_timeout

    def get_crypto_data(self, coin_name: str) -> Optional[CryptoData]:
        """
        Retrieve metadata for a specific cryptocurrency, using cache if available
        checks the cache for an existing entry before querying the data provider.
        if not cached, fetches from the provider and caches the result
        Args:
            coin_name (str): The name or symbol of the cryptocurrency
        
        Returns:
            Optional[Cryptodata]: The data object if found; otherwise None.
        """
        cache_key =f"crypto_data_{coin_name.lower()}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        data = self.provider.get_crypto_data(coin_name)
        if data:
            cache.set(cache_key, data, self.cache_timeout)

        return data
    
    def get_all_coins(self) -> List[str]:
        """
        Retrieve a list of all available cryptocurrency identifiers.
        Attempts to use a cached list, if not found, retrieves the list from the data provider

        Returns:
            List[str]: List of available coin names or symbols.
        """
        cache_key = "all_coins"
        cached_coins = self.cache.get(cache_key)

        if cached_coins:
            return cached_coins
        
        coins = self.provider.get_all_coins()
        cache.set(cache_key, coins, self.cache_timeout)
        return coins
    


#response generators
class GreetingResponseGenerator(ResponseGenerator):
    """A response generator for detecting and replying to user greetings in chatbot conversations."""
    def __init__(self):
        """Defines a dict "self.greetings" with regex patterns as keys and list of possible as values."""
        self.greetings = {
            r'hello|hi|hey|yo|sup': [
                "GM! Ready to talk some crypto?",
                "Hey there! What's cooking in the markets today?",
                "Yo! How's your portfolio looking?",
                "Hi! Let’s chase those green candles 🌱",
                "Sup legend! You here for alpha or vibes?"
            ],
            r'how are you|what\'s up|how\'s it going|you good|how you doing': [
                "Living that crypto life! Charts up, vibes up! 📈",
                "Just hodling and staying strong! How about you?",
                "Running on hopium and coffee! ☕️",
                "Stacking sats and dodging rug pulls 😎",
                "Watching the market like a hawk 👀"
            ],
            r'good morning|gm|morning': [
                "GM! Time to check those green candles! 🕯️",
                "Good morning! Ready to make some alpha today?",
                "GM fren! Let's get this crypto!",
                "Rise and shine, it’s blockchain time!",
                "Another day, another dollar-cost average 😤"
            ]
        }
    
    def can_handle(self, user_input: str, context: UsersContext) -> bool:#returns a bool
        """
        converts the user input to lowercase for case-insensitive matching.
        checks whether any of the defined regex patterns match the input
        returns true if a greeting pattern is matched; false otherwise
        """
        user_input_lower = user_input.lower()
        return any(re.search(pattern, user_input_lower) for pattern in self.greetings.keys())
    
    def generate_response(self, user_input: str, context: UsersContext) -> Dict[str, Any]:
        """
        Loops through each pattern in the greetings dictionary
        if a pattern matches the input, randomly selects one of its responses
        if the user's context contains favorite coins, randomly picks one
        appends a personalized question to the response
        returns a dictionary with the message and a type label ("greeting")
        """
        user_input_lower = user_input.lower()

        for pattern, responses in self.greetings.items():
            if re.search(pattern, user_input_lower):
                response = random.choice(responses)

                #personalize based on context
                if context.favorite_coins:
                    coin = random.choice(context.favorite_coins)
                    response += f" How's {coin.upper()} treating you?"

                return {"response": response, "type": "greeting"}
        
        return {"response": "Hey there! What's on your crypto mind?", "type": "greeting"}


class CryptoAnalysisGenerator(ResponseGenerator):
    """Handles crypto-specific questions and analysis"""

    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider
        self.question_patterns = [
            r"what about|tell me about|how about|info on",
            r'should i buy|worth buying',
            r'price prediction|will.*go up|will.*moon',
            r'compare.*to|vs|versus'
        ]

    def can_handle(self, user_input: str, context: UsersContext) -> bool:
        """Check if this generator can handle crypto-related questions"""
        user_input_lower = user_input.lower()
        
        # Check if any crypto-related patterns match
        pattern_match = any(re.search(pattern, user_input_lower) for pattern in self.question_patterns)
        
        # Also check if we can find a valid coin name in the input
        all_coins = self.data_provider.get_all_coins()
        best_match, score = process.extractOne(user_input_lower, all_coins)
        
        return pattern_match or score >= 70
        
    def generate_response(self, user_input: str, context: UsersContext) -> Dict[str, Any]:
        """Generate response for crypto-related questions"""
        user_input_lower = user_input.lower()

        # Extract coin name using fuzzy matching
        all_coins = self.data_provider.get_all_coins()
        best_match, score = process.extractOne(user_input_lower, all_coins)

        if score < 70:
            return {
                "response": "Hmm, I'm not sure which crypto you're asking about. Try asking about Bitcoin, Ethereum or Solana!",
                "type": "clarification"
            }
        
        crypto_data = self.data_provider.get_crypto_data(best_match)
        if not crypto_data:
            return {
                "response": f"I know {best_match} exists, but I don't have current data on it. My bad!",
                "type": "error"
            }
        
        # Generate contextual response based on question type
        if re.search(r"should I buy|worth buying", user_input_lower):
            response = self._generate_buy_advice(crypto_data, context)
        elif re.search(r"price prediction|will.*go up|will.*moon", user_input_lower):
            response = self._generate_prediction_response(crypto_data)
        else:
            response = self._generate_general_analysis(crypto_data)
        
        # Add to user's favorite coins
        if best_match not in context.favorite_coins:
            context.favorite_coins.append(best_match)

        return {
            "response": response,
            "format": "html",
            "type": "crypto_analysis",
            "coin": best_match
        }
    
    def _generate_buy_advice(self, crypto_data: CryptoData, context: UsersContext) -> str:
        risk_advice = {
            "low": "This looks pretty safe for your risk level.",
            "medium": "Moderate risk - matches your profile well.",
            "high": "This might be too spicy for your risk tolerance!",
            "very_high": "⚠️ HIGH RISK ALERT! Only if you can afford to lose it all."
        }

        advice = risk_advice.get(crypto_data.risk_level, "Do your own research!")

        return f"""
        <strong>{crypto_data.name.upper()} Buy Analysis</strong><br>
        <span class='trend'>Current Trend: {crypto_data.trend}</span><br>
        <span class='risk'>Risk Level: {crypto_data.risk_level}</span><br>
        <span class='verdict'>Take: {crypto_data.verdict}</span><br>
        <span class='advice'>My Advice: {advice} {crypto_data.advice}</span>
        """
    

    def _generate_prediction_response(self, crypto_data: CryptoData) -> str:
        disclaimer = [
            "🔮 Crystal ball says... nobody knows!",
            "📈 Past performance ≠ future results",
            "🎰 This is not financial advice!",
            "🚀 To the moon? Maybe, maybe not!"
        ]

        return f"""
        <strong>{crypto_data.name.upper()} Price Prediction</strong><br>
        <span class="disclaimer">{random.choice(disclaimer)}</span><br>
        <span class="trend">Current Trend: {crypto_data.trend}</span><br>
        <span class="verdict">Market Vibe: {crypto_data.verdict}</span><br>
        <span class="advice">Strategy: {crypto_data.advice}</span>
        """
    
    def _generate_general_analysis(self, crypto_data: CryptoData) -> str:
        freshness = "Fresh data" if not crypto_data.is_stale else "Slightly stale data"

        tags_display = " . ".join(f"#{tag}" for tag in crypto_data.tags[:3])

        return f"""
        <strong>{crypto_data.name.upper()}</strong> {freshness}<br>
        <span class='trend'>📊 Trend: {crypto_data.trend}</span><br>
        <span class='verdict'>💭 Verdict: {crypto_data.verdict}</span><br>
        <span class='advice'>💡 Advice: {crypto_data.advice}</span><br>
        <span class='tags'>🏷️ Tags: {tags_display}</span>
        """

class TrendAnalysisGenerator(ResponseGenerator):
    """Handles market trend analysis requests"""

    def __init__(self, data_provider: DataProvider):
        """
        Initializes the trend analysis generator with a data provider
        that can fetch coin data and trends.
        """
        self.data_provider = data_provider

    def can_handle(self, user_input: str, context: UsersContext) -> bool:
        """
        Returns True if the user's input suggests they are asking about:
            general market trends
            bullish/bearish conditions
            trending cryptocurrencies
            their personal portfolio/watchlist
        """
        patterns = [
            r'market trend|overall market|crypto market',
            r'what\'s hot|trending|popular',
            r'bull.*market|bear.*market',
            r'portfolio.*check|my.*coins'
        ]
        return any(re.search(pattern, user_input.lower()) for pattern in patterns)
    
    def generate_response(self, user_input: str, context: UsersContext) -> Dict[str, Any]:
        """
        Parses the user input and delegates response generation based on intent:
        portfolio summary (if user refers to my coins or portfolio check)
        market overview (default case)
        """
        user_input_lower = user_input.lower()

        if re.search(r"portfolio.*check|my.*coins", user_input_lower):
            return self.generate_portfolio_summary(context)
        else:
            return self._generate_market_overview()
        
    def _generate_portfolio_summary(self, context: UsersContext) -> Dict[str, Any]:
        """
        Generates an HTML summary of the user's last 5 favorite coins.
        Includes trend emojis and names
        if no favorites exist, prompts the user to start adding
        """
        if not context.favorite_coins:
            return {
                "response": "You haven't asked about coins yet! Try asking about Bitcoin or Ethereum to get started.",
                "type": "portfolio_empty"
            }
        
        summaries = []
        for coin in context.favorite_coins[-5:]: #Last 5 coins
            crypto_data = self.data_provider.get_crypto_data(coin)
            if crypto_data:
                trend_emoji = {"bullish": "🚀", "rising": "📈", "pump": "🔥"}.get(crypto_data.trend, "📊")
                summaries.append(f"{coin.upper()} {trend_emoji} {crypto_data.trend}")
            
        return {
            "response": f"<strong>Your Watchlist</strong><br>" + "<br>".join(summaries),
            "format": "html",
            "type": "portfolio_summary"
        }
    
    def _generate_market_overview(self) -> Dict[str, Any]:
        """
        analyzes trends across all available coins and determines the dominant market mood.
        returns an HTML-formatted summary including an emoji and advice
        """
        all_coins = self.data_provider.get_all_coins()
        trends = {}

        for coin in all_coins:
            crypto_data = self.data_provider.get_crypto_data(coin)
            if crypto_data:
                trend = crypto_data.trend
                trends[trend] = trends.get(trend, 0) + 1
        
        market_mood = max(trends, key=trends.get) if trends else "uknown"
        mood_emoji = {
            "bullish": "🚀", "rising": "📈", "pump": "🔥",
            "bearish": "📉", "dump": "💥", "volatile": "🎢"
        }.get(market_mood, "🤷‍♂️")

        return {
             "response": f"<strong>Market Overview</strong> {mood_emoji}<br>Overall mood: {market_mood}<br>Stay safe out there!",
            "format": "html",
            "type": "market_overview"
        }
    
class DefaultResponseGenerator(ResponseGenerator):
    """
    Fallback response generator to handle any user input
    that doesn't match specific patterns from other generators
    """

    def can_handle(self, user_input: str, context: UsersContext) -> bool:
        """
        always returns true, making this the default handler
        should be placed last in the handler chain
        """
        return True #always can handle as fallback
    
    def generate_response(self, user_input: str, context: UsersContext) -> Dict[str, Any]:
        """
        returns a default message when no other handler matches
        suggests sample queries and keeps the conversation going
        """
        responses = [
            "I'm your crypto companion! Ask me about Bitcoin, Ethereum, or any other coins!",
            "WAGMI! (We're All Gonna Make It) What crypto are you curious about?",
            "Not sure what you mean, but I'm here for all your crypto questions! 🚀",
            "Try asking: 'What about Bitcoin?' or 'Should I buy Ethereum?'"
        ]
        
        return {
            "response": random.choice(responses),
            "type": "default"
        }
    
#main services
class CryptoBotService:
    """
    Main orchestration service that handles user interactions and delegates response generation
    to appropriate modules based on the user input context. It manages session-specific state,
    dynamically fetches or injects cypto data, and supports extensible response generation logic.
    """
    def __init__(self):
        #initialize data provider with caching
        static_provider = StaticCryptoProvider()
        self.data_provider = CachedDataProvider(static_provider)

        #initialize response generators in priority order
        self.response_generators = [
            GreetingResponseGenerator(),
            CryptoAnalysisGenerator(self.data_provider),
            TrendAnalysisGenerator(self.data_provider),
            DefaultResponseGenerator() #always last as fallback
        ]

        #user context storage (in production, use database/redis)
        self.user_contexts: Dict[str, UsersContext] = {}

        self.logger = logging.getLogger(__name__)
    
    def get_user_context(self, session_id: str) -> UsersContext:
        """
        Retrieves or initializes the context object for a given session
        This allows the bot to maintain state (like past questions or favorite coins) per user.
        Args:
            session_id (str): Unique ID for the user's session.
        returns:
            userscontext: the user's session context.
        """
        if session_id not in self.user_contexts:
            self.user_contexts[session_id] = UsersContext(session_id=session_id)
        return self.user_contexts[session_id]
    
    def process_chat_message(self, user_input: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Main handler that:
            fetches/creates the user's context
            adds the latest message to chat history
            Iterates through the list of response gerators to find the first one that can handle the input.
            executes the matched generator's logic and returns its output
            Catches and logs any runtime errors without crashing the flow
        Args:
            user_input (str): The user's raw message input.
            session_id (str): The session ID to tie context to
        Returns:
            Dict[str, Any]: A structured response dict from the matched generator.
        """
        context = self.get_user_context(session_id)
        context.add_to_history(user_input)

        #find the first generator that can handle this input
        for generator in self.response_generators:
            if generator.can_handle(user_input, context):
                try:
                    response = generator.generate_response(user_input, context)
                    self.logger.info(f"Response generated by {generator.__class__.__name__}")
                    return response
                except Exception as e:
                    self.logger.error(f"Error in {generator.__class__.__name__}: {str(e)}")
                    continue


        #fallback response (should never reach here due to DefaultResponseGenerator)
        return {"response": "Something went wrong! Try again?", "type": "error"}
    
    def add_crypto_dynamically(self, crypto_data: CryptoData) -> None:
        """
        allow injection of  new crypto data  into the underlying data providerat runtime
        Args:
            crypto_data (CryptoData): The new coin data to be injected
        """
        if hasattr(self.data_provider, "provider") and hasattr(self.data_provider.provider, "add_crypto"):
            self.data_provider.provider.add_crypto(crypto_data)
            #clear cache for this coin
            cache_key = f"crypto_data_{crypto_data.name.lower()}"
            cache.delete(cache_key)
            cache.delete("all_coins")
    
    def get_crypto_advice(self, coin: str) -> Optional[CryptoData]:
        """
        get advice for a specific crypto
        calls the data provider with lowercase-normalized name.
        Args:
            coin (str): The coin name (e.g., "Bitcoin", "ETH").
        returns:
            Optional[CryptoData]: Analysis object for the coin, or None if unavailable.
        """
        return self.data_provider.get_crypto_data(coin.lower())

#global service instance
crypto_bot_service = CryptoBotService()

#django views
def home(request):
    """
    render the main chatbot user interface
    Purpose:
        load the frontend HTML for user interaction with the crypto bot.
    flow:
    Simply returns the index template
    """
    return render(request, "bot/index.html")

def crypto_advice(request, coin):
    """
    handle requests for specific cryptocurrency advice
    Purpose:
        provide analysis, trend and recommendations for a given coin
    
    Flow:
        uses the global service to retrieve data about the coin
        if coin not found: returns a 404-like humorous error.
        if found: structures and returns a rich json response with key metrics.
    """
    crypto_data = crypto_bot_service.get_crypto_advice(coin)

    if not crypto_data:
        return JsonResponse({
            "error": f"'{coin}'? Never heard of it. Are you making up coins now? 😅"
        }, status=404)
    
    return JsonResponse ({
        "coin": coin.upper(),
        "trend": crypto_data.trend,
        "verdict": crypto_data.verdict,
        "advice": crypto_data.advice,
        "risk_level": crypto_data.risk_level,
        "tags": crypto_data.tags,
        "sustainability_score": crypto_data.sustainability_score
    })

def chat_with_bot(request):
    """
    Handle general chat messages from users and returns AI-generated responses.
    Purpose:
        -capture input, identify user session, maintain context, generate dynamic replies.
    Flow:
        accepts only get requests.
        extracts message from query params
        ensures a valid session exists for context tracking.
        Delegates message handling to CryptoBotService, which uses NLP-like logic.
        Returns generated response in JSON
    """
    if request.method != "GET":
        return JsonResponse({"response": "Send me a Get request with your message!"})
    
    user_input = request.GET.get("message", "").strip()
    if not user_input:
        return JsonResponse({"response": "Send me a message to get started!"})
    
    #Get session ID (create one if doesn't exist)
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key

    #Process message with context
    response_data = crypto_bot_service.process_chat_message(user_input, session_id)

    return JsonResponse(response_data)

def add_crypto(request):
    """
    Admin-only endpoint to inject new crypto coins into the bot's runtime
    Purpose:
        allow real-time additions of coins and associated analysis via Post
    flow:
        Only accepts POST requests with raw JSON body
        Parses and validates required fields (name, trend, verdict...)
        Optional fields like sustainability score and tags are defaulted
        adds new crypto to backend, clears any cached version
        returns success or error in JSON.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"})
    
    try:
        data = json.loads(request.body)
        crypto_data = CryptoData(
             name=data['name'],
            trend=data['trend'],
            verdict=data['verdict'],
            advice=data['advice'],
            market_cap=data.get('market_cap', 'medium'),
            sustainability_score=data.get('sustainability_score', 5.0),
            tags=data.get('tags', [])
        )

        crypto_bot_service.add_crypto_dynamically(crypto_data)

        return JsonResponse({
            "message": f"Successfully added {crypto_data.name}!",
            "crypto": crypto_data.name
        })
    
    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({"Error": f"Invalid data: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"Error": f"Server error: {str(e)}"}, status=500)
    
def find_best_coin_match(input_text):
    """
    utility function to find the best fuzzy match for a crypto name from known data.
    Purpose:
        Support lenient matching for user typos or alternate spellings
    Flow:
        Fetchesb all known coins.
        Uses fuzzy matching (e.g., fuzzywuzzy) to score against input.
        returns best match if confidence is above 70% otherwise None
    """
    all_coins = crypto_bot_service.data_provider.get_all_coins()
    best_match, score = process.extractOne(input_text, all_coins)
    return best_match if score > 70 else None