---
permalink: /
layout: default
title: ""
pagination:
  enabled: true
---

<div id="main" role="main">
  {% include sidebar.html %}

  <div class="archive home">
    {% if paginator %}
      {% assign posts = paginator.posts %}
    {% else %}
      {% assign posts = site.posts %}
    {% endif %}

    {% assign entries_layout = page.entries_layout | default: 'list' %}
    <div class="entries-{{ entries_layout }}">
      {% for post in posts %}
        {% include archive-single.html type=entries_layout %}
      {% endfor %}
    </div>

    {% include paginator.html %}
  </div>
</div>