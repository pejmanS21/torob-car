"""The Pydantic AI agent that turns a Persian search sentence into a SearchIntent.
It has no tools and one output type: the LLM never writes SQL (spec §8.2)."""

from datetime import date

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.output import PromptedOutput

from core.text import jalali_year
from schemas.search import SearchIntent

OUTPUT_RETRIES = 2

_INSTRUCTIONS = """\
You convert one Persian used-vehicle search query (Divar marketplace, Iran) into a
SearchIntent. Extract only what the user stated; leave everything else unset.

Rules:
- The current Jalali year is {year}. Years are Jalali. «مدل ۹۸» means 1398, «مدل ۰۲»
  means 1402. «مدل ۹۸» sets year_min = year_max = 1398. «۹۵ به بالا» sets only
  year_min = 1395. «تا مدل ۹۰» sets only year_max.
- All money is in toman as a full integer. «۸۰۰ میلیون» = 800000000. «۱.۲ میلیارد»
  = 1200000000. A bare number under 5 after «زیر/تا» means billions («زیر ۱.۲» =
  1200000000); a bare number of 5 or more means millions («زیر ۸۰۰» = 800000000).
  «زیر/تا/حداکثر/سقف» set price_max; «از/حداقل/بالای» set price_min.
- km_max is in kilometres: «زیر ۵۰ هزار کیلومتر» = 50000. «کم‌کارکرد» = 90000.
- vehicles: copy the brand, model and trim words exactly as the user wrote them, in
  Persian. Do not translate, expand or guess. «۲۰۶ تیپ ۲» → brand «پژو», model «۲۰۶»,
  trim «تیپ ۲». Several vehicles → several entries.
- category: light = passenger cars and pickups, motorcycle, heavy = trucks, buses,
  agricultural and construction machinery, rental, classic. Set it only when clear.
- cities: Persian city names exactly as written.
- gearbox: «اتومات/اتوماتیک/اتمات» → automatic, «دنده‌ای/دستی» → manual.
  Keep gearbox words out of vehicle model/trim. «دنا پلاس اتمات» means
  vehicles=[{{model: دنا پلاس}}], gearbox=automatic; do not invent a turbo or trim.
- only_below_market: true for «ارزان», «زیر قیمت», «به‌صرفه».
- sort: price for «ارزان‌ترین», km for «کم‌کارکردترین», newest for «جدیدترین»;
  otherwise relevance.
- text: any remaining descriptive words (e.g. «شاسی‌بلند», «خانوادگی»); else unset.

Examples:
«۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران» → vehicles=[{{brand: پژو, model: ۲۰۶}}],
  year_min=1398, year_max=1398, price_max=800000000, cities=[تهران]
«دنا پلاس اتومات تا یک و نیم میلیارد کرج یا تهران» → vehicles=[{{model: دنا پلاس}}],
  gearbox=automatic, price_max=1500000000, cities=[کرج, تهران]
«موتور هوندا ۱۲۵ کم‌کارکرد» → category=motorcycle,
  vehicles=[{{brand: هوندا, model: ۱۲۵}}], km_max=90000
«یه شاسی‌بلند سفید زیر ۳ میلیارد» → price_max=3000000000, colors=[سفید],
  text=شاسی‌بلند
«کامیون بنز ده تن» → category=heavy, text=کامیون بنز ده تن
"""


def build_instructions() -> str:
    return _INSTRUCTIONS.format(year=jalali_year(date.today()))


def build_intent_agent(model: Model) -> Agent[None, SearchIntent]:
    return Agent(
        model,
        # PromptedOutput, not the default tool output: a thinking model rejects the
        # forced `tool_choice` an output tool needs ("Thinking mode does not support
        # this tool_choice"), and DeepSeek rejects NativeOutput's `json_schema`
        # response format too. This puts the schema in the instructions and uses
        # plain JSON mode, which every provider here accepts.
        output_type=PromptedOutput(SearchIntent),
        instructions=build_instructions,
        retries=OUTPUT_RETRIES,
    )
