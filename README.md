# About

gevent + httplib2 w/ cookie handling + keep alive + heuristics for increased crawling spread

# Usage

```
from spider.spider import Spider
google = Spider.site('www.google.com', workers=5, robots=False, sitemap=False, cookies=True)
google.scope.allow.add(domain='youtube.com')
google.scope.allow.add(domain='*.youtube.com')
google.scope.reject.add(domain='plus.google.com')


from plugins import response
google.events.register(response.Handler())

google.crawl()
```

See `spider/spider.py`, `spider/scope.py`, `spider/event.py` for more details.

# TODO

## Increase Spread

* add random value to rating staying within group bounds

## HTML form

* select

```
<form>
    <select>
        <option name="" value="">
    </select> 
</form>
```

* checkbox

```
<form>
    <input type="checkbox" name="" value"">
</form>
```

* radio

```
<form>
    <input type="radio" name="1" value"" checked>
    <input type="radio" name="1" value"">
</form>
```

* file

```
<form>
    <input type="file" name="">
</form>
```

## HTTP(S) proxy

* socksipy ?

## Javascript

* ghost.py ?
